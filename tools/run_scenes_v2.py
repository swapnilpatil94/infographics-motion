import sys, traceback, time; sys.path.insert(0,'.')
from engine.skeleton import v2_scenes as S
for k in sys.argv[1:] or ["interaction","parallax","lighting"]:
    t=time.time()
    try:
        S.run(k); print("OK",k,round(time.time()-t),"s",flush=True)
    except Exception:
        print("FAIL",k,flush=True); traceback.print_exc()
