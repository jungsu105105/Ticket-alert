import os, re, time, requests
from urllib.parse import quote
from playwright.sync_api import sync_playwright

BASE = "https://m.booking.naver.com/booking/12/bizes/233651/items/3056171"
DATES = ["2026-10-10", "2026-11-07"]
TIME_TEXT = "7:20"
NEED = 2
ROUNDS = 3        # 한 번 실행할 때 확인하는 횟수
WAIT = 60         # 확인 사이 간격(초)
TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")


def url_for(d):
    dt = quote(f"{d}T00:00:00+09:00", safe="")
    return f"{BASE}?area=plt&lang=ko&startDateTime={dt}&theme=place"


def notify(msg):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg},
        timeout=10,
    )
    print("텔레그램 응답:", r.status_code)


def check(page, d):
    page.goto(url_for(d), wait_until="domcontentloaded", timeout=30000)
    try:
        page.get_by_text(re.compile(re.escape(TIME_TEXT))).first.wait_for(timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    slots = page.get_by_text(re.compile(re.escape(TIME_TEXT))).all()
    if not slots:
        return False, "7:20 회차 없음"
    for el in slots:
        box = el.locator("xpath=ancestor-or-self::*[self::button or self::li or self::a][1]")
        t = box.first if box.count() else el
        text = t.inner_text().replace("\n", " ")
        cls = (t.get_attribute("class") or "").lower()
        bad = (
            t.get_attribute("disabled") is not None
            or t.get_attribute("aria-disabled") == "true"
            or "disabled" in cls
            or "sold" in cls
        )
        if "매진" in text or bad:
            return False, f"매진: {text}"
        m = re.search(r"(\d+)\s*(석|장|명|개)", text)
        if m and int(m.group(1)) < NEED:
            return False, f"잔여 부족: {text}"
        return True, text
    return False, "판단 불가"


if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
    notify("✅ 테스트 알림: 연결 성공!")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(
        locale="ko-KR",
        viewport={"width": 390, "height": 844},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    page = ctx.new_page()
    done = False
    for i in range(ROUNDS):
        for d in DATES:
            try:
                ok, info = check(page, d)
            except Exception as e:
                ok, info = False, f"오류: {e}"
            print(time.strftime("%H:%M:%S"), ">>>", d, "가능" if ok else "불가", "|", info)
            if ok:
                notify(f"🎫 {d} 오후 7:20 자리 생김! ({NEED}장)\n{url_for(d)}")
                done = True
        if done:
            break
        if i < ROUNDS - 1:
            time.sleep(WAIT)
    b.close()
