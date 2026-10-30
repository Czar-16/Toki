# Toki managed function. Resolve the checkout even when loaded through a symlink.
function __toki_root
    path dirname (path dirname (path resolve (status filename)))
end
