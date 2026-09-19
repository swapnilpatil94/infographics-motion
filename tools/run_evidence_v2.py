import sys, traceback, time; sys.path.insert(0,'.')
from engine.skeleton import v2_evidence as E
jobs=[("sheet50",lambda:E.sheet50(50)),("rig_motion_v2",E.rig_motion_v2),("face_expression_test",E.face_expression_test),("eye_gaze_test",E.eye_gaze_test),
      ("hand_pose_test",E.hand_pose_test),("same_identity_views",E.same_identity_views),("10_character_same_rig",E.ten_same_rig),("crowd_test_v2",E.crowd_v2)]
only=sys.argv[1:]
for name,fn in jobs:
    if only and name not in only: continue
    t=time.time()
    try:
        r=fn(); print("OK",name,round(time.time()-t),"s",flush=True)
    except Exception:
        print("FAIL",name,flush=True); traceback.print_exc()
