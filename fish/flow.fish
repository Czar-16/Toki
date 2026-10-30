# Toki managed function.
function flow --description "Start Toki focus and break sessions"
    if test (count $argv) -eq 1
        switch "$argv[1]"
            case stats
                python3 (__toki_root)/stats.py
                return $status
            case -h --help help
                printf '%s\n' 'Toki — study timer' '' \
                    'Usage: toki [duration | stats | --help]' \
                    'Examples: toki 25, toki 30s, toki 1.5h, toki stats' \
                    'No duration: choose a countdown or open-ended study.' '' \
                    'Space or p: pause/resume | q or Ctrl+C: stop' \
                    'Enter finishes an open-ended session.'
                return 0
        end
    end
    flowmodoro $argv
end
