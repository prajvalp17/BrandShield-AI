"""Generates the SIMULATED starter dataset (v2: contact_number, redirect_url, expected_ring). 
Run: python make_data.py   — edit and extend freely."""
import json
from collections import Counter

BRANDS = [
 dict(brand_id="brand_01", name="Zenbank", h="zenbank", dom="zenbank.example", sw1="z3nbank", sw2="zembank",
      pkg="com.zenbank.mobile", pkg2="com.zenbank.insights", pub="Zenbank Ltd", phone="+91 80000 10001"),
 dict(brand_id="brand_02", name="PayNest", h="paynest", dom="paynest.example", sw1="payn3st", sw2="paynesl",
      pkg="com.paynest.wallet", pkg2="com.paynest.business", pub="PayNest Technologies", phone="+91 80000 20001"),
 dict(brand_id="brand_03", name="QuickCart", h="quickcart", dom="quickcart.example", sw1="qu1ckcart", sw2="qulckcart",
      pkg="com.quickcart.shop", pkg2="com.quickcart.partner", pub="QuickCart Retail Pvt Ltd", phone="+91 80000 30001"),
]
RING_A = dict(phone="+91 90000 11111", url="http://secure-verify-login.example/auth")   # shared phone + redirect
RING_B_URL = "http://unlock-account.example/pay"                                          # shared redirect only
NEAR_MISS_PHONE = "+91 90000 11112"                                                       # one digit off Ring A
SHARED_BENIGN_PHONE = "+91 70000 55555"                                                   # benign accounts, same publisher

registry = {"brands": [{
    "brand_id": b["brand_id"], "name": b["name"],
    "official_handles": {"Instagram": [f"@{b['h']}", f"@{b['h']}_support"], "X": [f"@{b['h']}", f"@{b['h']}_care"]},
    "official_domains": [b["dom"], f"support.{b['dom']}"],
    "official_apps": [{"platform": "Android", "package_id": b["pkg"], "publisher": b["pub"]},
                      {"platform": "Android", "package_id": b["pkg2"], "publisher": b["pub"]}],
    "official_contact_numbers": [b["phone"]],
    "evidence_source": "simulated"} for b in BRANDS]}

uniq = [20000]
def unique_phone():
    uniq[0] += 1
    return f"+91 90000 {uniq[0]}"

social, apps = [], []
def add_social(b, platform, user, disp, bio, age, phone, url, truth, note, ring=None):
    social.append(dict(entity_id=f"soc_{len(social)+1:02d}", target_type="social_profile", brand_id=b["brand_id"],
        platform=platform, username=user, display_name=disp, bio=bio, account_age_days=age,
        contact_number=phone, redirect_url=url, evidence_source="simulated",
        ground_truth=truth, category_note=note, expected_ring=ring))
def add_app(b, name, pkg, pub, desc, phone, url, truth, note, ring=None):
    apps.append(dict(entity_id=f"app_{len(apps)+1:02d}", target_type="app_listing", brand_id=b["brand_id"],
        platform="Android", app_name=name, package_id=pkg, publisher=pub, description=desc,
        contact_number=phone, redirect_url=url, evidence_source="simulated",
        ground_truth=truth, category_note=note, expected_ring=ring))

for i, b in enumerate(BRANDS):
    h, N, d, P = b["h"], b["name"], b["dom"], b["phone"]
    # OFFICIAL
    add_social(b,"Instagram",f"@{h}",f"{N} Official",f"Official account of {N}.",2400,P,f"https://{d}","official","main registered handle")
    add_social(b,"X",f"@{h}_care",f"{N} Care","Customer care. We never ask for OTP or PIN.",1800,P,f"https://support.{d}","official","registered handle; bio mentions OTP safely")
    add_social(b,"Instagram",f"@{h}_support",f"{N} Support","Help and support for customers.",None,None,f"https://support.{d}","official","registered handle; missing age and phone")
    # IMPERSONATORS
    add_social(b,"Instagram",f"@{b['sw1']}",f"{N} Official","Official page. Verify your account now to avoid suspension.",12,RING_A["phone"],RING_A["url"],"impersonator","character swap + urgent verification (Ring A)","ring_A")
    add_social(b,"X",f"@{h}_helpdesk_official",f"{N} Helpdesk","Share your OTP here to resolve issues instantly.",5,
               NEAR_MISS_PHONE if i == 0 else unique_phone(), f"http://helpdesk-{h}.example/chat","impersonator",
               "added words + OTP request" + ("; phone one digit off Ring A (must NOT link)" if i == 0 else ""))
    add_social(b,"Instagram",f"@{b['sw2']}",f"{N} Rewards",f"Pay a small processing fee to claim your {N} reward.",20,unique_phone(),f"http://claim-{h}.example/fee","impersonator","lookalike letters + payment request")
    add_social(b,"X",f"@{h}.support.team",f"{N} Support Team","Urgent: account blocked. Send payment to unlock.",3,unique_phone(),RING_B_URL,"impersonator","new account + urgent payment (Ring B: shared redirect only)","ring_B")
    # BENIGN
    add_social(b,"Instagram",f"@{h}_fans",f"{N} Fan Club",f"Unofficial fan community for {N} users. Not affiliated.",900,SHARED_BENIGN_PHONE,f"https://linkhub.example/{h}_fans","benign","fan page; shares phone with news page (benign, no ring)")
    add_social(b,"X",f"@{h}_news_daily",f"{N} News","Daily news and reviews about the industry.",1500,SHARED_BENIGN_PHONE,f"https://linkhub.example/{h}_news","benign","news page; same linkhub domain, different path")
    add_social(b,"Instagram",f"@{h[:-2]}y_{h[-3:]}s","Personal account","Just posting my travel photos.",700,None,None,"benign","unrelated name resembling brand")

# hard cases
add_social(BRANDS[0],"Instagram","@zenbank_offers","Zenbank Offers","Great deals every week!",30,None,None,"benign","HARD: suspicious name, harmless bio")
add_social(BRANDS[1],"X","@my_wallet_tips","Wallet Tips","Verify your account settings in the PayNest app menu - guide.",600,None,None,"benign","HARD: scam-like phrase, educational, unrelated handle")
add_social(BRANDS[2],"Instagram","@quickkcart","QuickCart","Order now. Send advance payment on this page.",8,unique_phone(),"http://qc-advance.example/pay","impersonator","HARD: repeated letter, payment request, no official claim")

for i, b in enumerate(BRANDS):
    N, h, P = b["name"], b["h"], b["phone"]
    add_app(b,N,b["pkg"],b["pub"],f"Manage your {N} account securely.",P,f"https://{b['dom']}","official","registered package + publisher")
    add_app(b,f"{N} Insights" if h != "quickcart" else f"{N} Partner",b["pkg2"],b["pub"],f"Companion app from {N}.",P,f"https://{b['dom']}","official","second registered app")
    ringA = i < 2   # cross-platform link to the social Ring A
    add_app(b,f"{N} Rewards",f"com.{h}.rewards.apk","Fast Cash Apps",f"Login with your {N} card number to claim rewards.",
            RING_A["phone"] if ringA else unique_phone(), RING_A["url"] if ringA else f"http://apk-{h}.example/get","impersonator",
            "name match + publisher mismatch + credential bait" + (" (Ring A, cross-platform)" if ringA else ""), "ring_A" if ringA else None)
    add_app(b,f"{N} Mobile Pro",f"com.{h}mobile.pro","Mobi Studio Co",f"The best way to use {N}. Same features as the official {N} app.",unique_phone(),None,"impersonator","copied description + similar package")
    add_app(b,f"{N} Calculator",f"com.calc.tools.{h}","Everyday Tools",f"Simple calculator. Not affiliated with {N}.",None,"https://everyday-tools.example","benign","unrelated utility mentioning brand")
add_app(BRANDS[1],"Budget Tracker for PayNest Users","com.thirdparty.budgettrack","Ledger Labs","Track spending from your exported statements. Independent tool.",None,"https://ledgerlabs.example","benign","HARD: legit third-party tool using brand name")

# sanity checks
ids = [r["entity_id"] for r in social + apps]
assert len(ids) == len(set(ids))
names = [(r["platform"], r["username"]) for r in social]
assert len(names) == len(set(names)), "duplicate handle"
official_handles = {h for b in registry["brands"] for hs in b["official_handles"].values() for h in hs}
for r in social:
    assert (r["username"] in official_handles) == (r["ground_truth"] == "official"), r["entity_id"]

for path, obj in (("data/brand_registry.json", registry), ("data/social_profiles.json", social), ("data/app_listings.json", apps)):
    json.dump(obj, open(path, "w"), indent=2)
print("social", len(social), dict(Counter(r["ground_truth"] for r in social)))
print("apps  ", len(apps), dict(Counter(r["ground_truth"] for r in apps)))
print("rings ", dict(Counter(r["expected_ring"] for r in social + apps if r["expected_ring"])))
