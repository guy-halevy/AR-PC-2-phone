"""Apply the already-validated dependency-lock repair to the pinned ALVR streamer."""
from pathlib import Path
import sys
p = Path(sys.argv[1])/'alvr/xtask/src/main.rs'
s = p.read_text()
a = 'build::build_streamer(profile, true, gpl, None, false, profiling, keep_config)'
b = 'build::build_streamer(profile, true, gpl, None, true, profiling, keep_config)'
if b not in s:
    if s.count(a) != 1: raise RuntimeError('Pinned ALVR source changed')
    p.write_text(s.replace(a,b))
