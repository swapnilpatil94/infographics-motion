import json
ENV = dict(
    bed=dict(type="generic", subject="bedroom", asset_id="env_bedroom", time_of_day="night"),
    atm=dict(type="generic", subject="ATM booth", asset_id="env_atm", time_of_day="night"),
    bank=dict(type="generic", subject="bank branch", asset_id="env_bank", time_of_day="day"),
    police=dict(type="generic", subject="cyber cell / police station", asset_id="env_police", time_of_day="day"),
)
def V(n, env, act, shot, mv, subj, emo, intent="SHOW_ACTION", chars=("C01",), props=(), share=None, params=None, screen=None, trans="cut", why=""):
    v = dict(narration_id=n, visual_intent=intent, environment=ENV[env], characters=list(chars), props=[dict(name=p) for p in props],
             action=dict(capability=act, actor="C01", params=params or {}), emotion=emo, camera=dict(shot=shot, movement=mv, subject=subj), effects=[], transition=trans, rationale=why)
    if share: v["share"] = share
    if screen: v["screen"] = screen
    return v
vs = [
 V("N01","bed","ESTABLISH","wide","push","environment","neutral","ESTABLISH_LOCATION",why="hook: night, alone, the room closing in"),
 V("N02","bed","PHONE_ALERT","two_reach","reveal","protagonist_reach","confusion",props=["phone"],why="the unknown call lights the phone"),
 V("N03","bed","REACH_PHONE","full","hold","protagonist_full","suspicion",props=["phone"],why="he reaches for it"),
 V("N04","bed","PICK_UP","close","push","protagonist_phone","suspicion","BUILD_TENSION",props=["phone"],why="the phone at his ear: the voice begins"),
 V("N05","bed","PHONE_CALL","medium","isolate","protagonist_head","confusion",props=["phone"],share=0.5,why="listening to the caller"),
 V("N05","bed","EYES_CHANGE","close","push","protagonist_head","fear","EMOTIONAL_REACTION",share=0.5,why="'account will close now': fear"),
 V("N06","bed","STAND_UP","full","pull","protagonist_full","fear","BUILD_TENSION",props=["phone"],why="panic: he stands up and gives the OTP"),
 V("N07","bed","LOOK_AT_PHONE","close","push","protagonist_phone","fear","REVEAL_INFORMATION",props=["phone"],why="the phone buzzes again"),
 V("N08","bed","INSERT_SCREEN","medium","hold",None,"realization","REVEAL_INFORMATION",share=0.5,screen=dict(sender="BK-ALERT",text="खाते से 48,000 रुपये कट गए।"),why="the debit alert, full screen"),
 V("N08","bed","VISUALIZE_FLOW","close","hold",None,"realization","EXPLAIN_PROCESS",share=0.5,params=dict(amount=48000,from_label="रोहन का खाता",to=["अनजान खाता"]),why="the money leaving his account"),
 V("N09","atm","ARRIVE","full","track","protagonist_full","fear","TIME_PASSAGE",trans="fade",why="he runs to the ATM"),
 V("N10","atm","USE_ATM","two_reach","drift","protagonist_reach","fear",props=["atm","card"],why="checking the balance"),
 V("N11","atm","REALIZE","close","push","protagonist_head","sadness","REALIZATION",why="the money is really gone"),
 V("N12","bank","ARRIVE","full","track","protagonist_full","neutral","TIME_PASSAGE",trans="fade",why="next morning, the bank"),
 V("N13","bank","MEET","reveal","pull","two_shot","neutral","INTRODUCE_CHARACTER",chars=("C01","C02"),why="the bank employee is waiting"),
 V("N14","bank","CONVERSE","two","drift","two_shot","hope",chars=("C01","C02"),share=0.55,why="the employee explains"),
 V("N14","bank","REALIZE","close","hold","protagonist_head","realization","REALIZATION",share=0.45,why="he understands: banks never ask for an OTP"),
 V("N15","police","ARRIVE","full","track","protagonist_full","neutral","TIME_PASSAGE",trans="fade",share=0.45,why="the cyber cell"),
 V("N15","police","READ_DOCUMENT","medium","push","protagonist_head","suspicion",props=["document","pen"],share=0.55,why="he fills the complaint form"),
 V("N16","police","VISUALIZE_FLOW","medium","hold",None,"relief","CONSEQUENCE",share=0.55,params=dict(amount=20000,from_label="रुका हुआ पैसा",to=["रोहन का खाता"]),why="20,000 comes back because he complained in time"),
 V("N16","police","OBSERVE","full","hold","protagonist_full","relief",share=0.45,why="relief: he lets out a breath"),
 V("N17","police","EYES_CHANGE","medium","drift","protagonist_head","realization",why="'remember': he turns to us"),
 V("N18","police","CLOSE_UP","close","isolate","protagonist_head","realization","CLIMAX",why="the message to the viewer: never share the OTP"),
 V("N19","police","INSERT_SCREEN","medium","hold",None,"hope","REVEAL_INFORMATION",share=0.45,screen=dict(sender="साइबर हेल्पलाइन",text="ठगी हो तो तुरंत कॉल कीजिए: 1930"),why="the helpline card"),
 V("N19","police","RESOLVE","wide","pull","environment","relief","CONSEQUENCE",share=0.55,why="calm wide shot, warm light returns"),
]
plan = dict(title="ओटीपी के बाद", cast=[
  dict(id="C01", role="protagonist", archetype="young man", gender="male", name="रोहन", description="a young man", asset_id="char_young_man"),
  dict(id="C02", role="partner", archetype="bank employee", gender="either", name="बैंक कर्मचारी", description="a bank employee", asset_id="char_bank_employee")], visuals=vs)
json.dump(plan, open("director_reply.json","w"), ensure_ascii=False, indent=1)
print(len(vs), "visuals")
