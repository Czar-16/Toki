# Toki managed function. Adapted from mohsince-04/fish-flowmodoro (MIT).
function __flowmodoro_format_time
    set total_seconds (math "floor($argv[1])")
    set hours (math "floor($total_seconds / 3600)")
    set minutes (math "floor(($total_seconds % 3600) / 60)")
    set seconds (math "$total_seconds % 60")

    set formatted ""
    if test $hours -gt 0
        set formatted "$formatted$hours hour"
        if test $hours -ne 1
            set formatted "$formatted"s
        end
        set formatted "$formatted "
    end
    if test $minutes -gt 0
        set formatted "$formatted$minutes minute"
        if test $minutes -ne 1
            set formatted "$formatted"s
        end
        set formatted "$formatted "
    end
    if test $seconds -gt 0 || test -z "$formatted"
        set formatted "$formatted$seconds second"
        if test $seconds -ne 1
            set formatted "$formatted"s
        end
    end
    echo $formatted
end

function __flowmodoro_parse_duration
    set -l value (string lower -- (string trim -- "$argv[1]"))
    string match -rq '^[0-9]+([.][0-9]+)?[smh]?$' -- "$value"; or return 1
    set -l multiplier 60
    switch (string sub -s -1 -- "$value")
        case s
            set multiplier 1
        case h
            set multiplier 3600
    end
    set -l amount (string replace -r '[smh]$' '' -- "$value")
    set -l seconds (math "floor($amount * $multiplier)" 2>/dev/null); or return 1
    string match -rq '^[0-9]+$' -- "$seconds"; or return 1
    test "$seconds" -gt 0; or return 1
    echo $seconds
end

function __flowmodoro_countdown
    set -l result_file (mktemp); or return 2
    set -g __flowmodoro_active_seconds 0
    python3 (__toki_root)/countdown.py "$argv[1]" "$argv[2]" "$result_file"
    set -l timer_status $status
    if test -s "$result_file"
        set -g __flowmodoro_active_seconds (cat "$result_file")
    end
    command rm -f "$result_file"
    return $timer_status
end

function flowmodoro
    set -l initial_duration "$argv[1]"
    if test (count $argv) -gt 1
        echo 'Usage: toki [duration] — e.g. toki 25, toki 30s, toki 1h (flow also works)' >&2
        return 2
    end
    if test -n "$initial_duration"
        __flowmodoro_parse_duration "$initial_duration" >/dev/null; or begin
            echo 'Enter a positive duration: 25 (minutes), 30s, 25m, or 1h.' >&2
            return 2
        end
    end
    set -g overall_work_time 0
    set -g total_sessions 0

    function __flowmodoro_play_audio
        python3 (__toki_root)/audio.py "$argv[1]"
        sleep 0.2
    end

    while true
        # Choose a countdown, or retain the original open-ended work session.
        set -l target_duration 0
        while true
            set -l duration_input
            if test -n "$initial_duration"
                set duration_input "$initial_duration"
                set initial_duration ''
            else
                read -P 'Work duration (minutes, 30s, 1h; Enter = open-ended): ' duration_input; or return
            end
            if test -z (string trim -- "$duration_input")
                break
            end
            set target_duration (__flowmodoro_parse_duration "$duration_input")
            if test $status -eq 0
                break
            end
            echo 'Enter a positive duration: 25 (minutes), 30s, 25m, or 1h.'
        end

        # Work session
        __flowmodoro_play_audio startwork
        if test "$target_duration" -gt 0
            echo "Work Duration:" (__flowmodoro_format_time $target_duration)
        end
        read -P "Press ENTER to start working... " -l start_choice; or return
        __flowmodoro_play_audio workstatus
        echo "▶ Work session started at "(date +%H:%M:%S)

        # Both modes track and persist active study time, including early stops.
        __flowmodoro_countdown "$target_duration" Work; or return $status
        set work_duration $__flowmodoro_active_seconds
        if test "$target_duration" -gt 0
            echo '✓ Work timer finished!'
        end

        # Breaks are 20% of work, between 12 seconds and 30 minutes.
        set break_duration 0
        set actual_break 0
        if test $work_duration -ge 60
            set break_duration (math "floor(max(min($work_duration * 0.2, 1800), 12))")
        end

        # Break handling
        if test $break_duration -gt 0
            __flowmodoro_play_audio startbreak
            read -P "⏸ Break time. Press Enter." -l break_choice; or return
            echo "Break Duration:" (__flowmodoro_format_time $break_duration)
            __flowmodoro_play_audio breakstatus
            if __flowmodoro_countdown "$break_duration" Break
                set actual_break $__flowmodoro_active_seconds
                __flowmodoro_play_audio focus
            else
                set actual_break $__flowmodoro_active_seconds
                echo "Break interrupted after "(__flowmodoro_format_time $actual_break)
            end
        else
            echo "Session too short (<1m), no break needed"
        end

        # Update totals
        set overall_work_time (math "$overall_work_time + $work_duration")
        set total_sessions (math "$total_sessions + 1")

        # Session report
        printf "\nSession %s:\n" $total_sessions
        echo "├ Work:   "(__flowmodoro_format_time $work_duration)
        echo "├ Break:  "(if test $actual_break -gt 0
            __flowmodoro_format_time $actual_break
        else
            echo "0 seconds"
        end)
        echo "└ Total:  "(__flowmodoro_format_time $overall_work_time)

        # Continue prompt
        set -l continue true
        while true
            read -P "Continue? (Y/n) " -l choice; or return
            switch (string lower "$choice")
                case y yes ""
                    break
                case n no
                    set continue false
                    break
            end
        end
        if not $continue
            break
        end
    end

    # Final report
    printf "\nToki Summary:\n"
    echo "├ Total time:   "(__flowmodoro_format_time $overall_work_time)
    echo "├ Sessions:     $total_sessions"
    echo "└ Avg session:  "(__flowmodoro_format_time (math "$overall_work_time / $total_sessions"))

    # Final feedback
    if test $overall_work_time -ge 25200  # 7 hours
        __flowmodoro_play_audio didgreat
        echo "🚀 Phenomenal achievement!"
    else if test $overall_work_time -ge 14400  # 4 hours
        __flowmodoro_play_audio welltried
        echo "🎯 Great consistency!"
    else
        __flowmodoro_play_audio focus
        echo "💡 Every minute counts!"
    end
end
