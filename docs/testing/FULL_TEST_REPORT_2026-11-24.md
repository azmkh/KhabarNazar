# KhabarNazar — full test pass, 2026-11-24

This report replaces Section 6.9–6.10 of the FYP report and is the regression baseline for later fixes. Every result below was produced by running the case on this date; nothing is copied from earlier reports. Raw data: `backend/tests/full_pass/results_2026-11-24.json` / `.csv`; screenshots: `backend/tests/full_pass/screenshots/`.

## 1. Summary

- **198 test cases** (the report's 41 IDs kept and re-run, plus new ones): **176 passed, 6 failed, 7 known limitations, 1 not executed (blocked), 8 information-only records.**
- **6 defects**: Critical 0, High 0, Medium 3, Low 3. No crash, data leak between users, data loss or invented result was found.
- Every inference ran the real models (Urdu XLM-R, Roman Urdu XLM-R large, TF-IDF, EasyOCR, CLIP + DINOv2 + ResNet18 ensemble, Grad-CAM). Mocks were used only for fault injection, marked *Fault-injected*.
- This pass checks behaviour, not accuracy: inputs are synthetic and unlabelled, so a Fake/Real verdict is never a pass or fail in itself.

## 2. Environment

| Item | Value |
|---|---|
| Machine | Windows 11 Home (build 26300), Intel Core i5-1135G7 (4 cores / 8 threads), 15.7 GB RAM, Intel Iris Xe (no CUDA: CPU inference) |
| Software | Python 3.14.4 (backend venv), Node 24.15.0, Expo CLI 58.1.21 (expo ~58.0.26), Microsoft Edge (headless) for the web UI |
| Branch / commit | `deploy` at `99f58ae` **plus uncommitted Phase 2 files** (backend/.env.example, app/config.py, tests/test_deployment.py, scripts/migrate_to_neon.py; fingerprint `1c2c41517cb08bdc`). The commit to make them part of the tip was blocked by the session's permission system, so the code tested is `99f58ae` + those changes; they only add an inactive settings overlay and a migration script. |
| Applies to main? | `main` (`ef98609`, the university PC) has the same app code except the deploy additions: rate limits (TC-RL), TRUST_PROXY_HEADERS (TC-LOG-14), CORS_ORIGIN_REGEX (TC-SEC-05 regex origins), Neon pool and /health model status (TC-SEC-07). All other results and all 6 defects apply to both. |
| Urdu model | release `urdu-xlmr-v1`, `text_module/urdu/models/xlmr`, version `xlmr-urdu`, 256 tokens, labels {0: real, 1: fake}, KHABARNAZAR_URDU_XLMR_DIR unset; SHA-256 model.safetensors `651ddc795904500d185cce23abe773bea4ff15564cb2d894d8ade21f96516a32` |
| Roman Urdu model | `text_module/roman_urdu/models/xlmr`, `xlmr-roman-urdu` (XLM-R large), 512 tokens, {0: Real, 1: Fake}; SHA-256 `f73d789a5ba543225d380d288c517381d02c58cfeea0e1c771e071da57eee4bd` |
| Long Urdu articles | `tfidf-urdu-long-articles` (> 150 words), {0: Real, 1: Fake}; SHA-256 `c209b64254505a99a32fe8cfecb2d8a31517be12c1f25be2e6451ef91302a552` |
| Image ensemble | CLIP ViT-L/14 head `75062f7b…5709`, DINOv2-L head `8a9d91dc…8d2f`, ResNet18 robust `93bf9770…f2c2` (`image_module/models`); HF revisions CLIP `32bd6428`, DINOv2 `47b73eef`; real if P(real) ≥ 0.5 |
| EasyOCR | ur + en, `backend/.cache/easyocr` (arabic.pth `2a9afd42…`, craft_mlt_25k.pth `4a5efbfb…`); usable text: ≥ 10 letters and confidence ≥ 0.3 |
| Baseline suites (preflight) | pytest 167 passed / 13 skipped; pytest --postgres 167 / 13; --real-models -m real_models 13 passed (all real-model tests 180); text_module/tests 3 passed; alembic current e5b1c7a3d920, check: no changes; describe_database --check: match; tsc clean; expo-doctor 20/20. Audit had 156/13: +9 deploy tests, +2 Phase 2 tests. |
| Test servers | Throwaway uvicorn on 8001 (fresh SQLite from the Alembic migrations, own uploads folder, throwaway JWT secret, check limit raised to 1000/min by env); the same against the isolated `khabarnazar_test` PostgreSQL (wiped first); a real-limits server on 8002 (10/min, 1-minute lockout); fault cases in-process. The real `khabarnazar` database was never used. |
| Accounts | Users A, B, T (text), I (image) and others per case; admin = register + `scripts/set_user_role.py` (Backend Guide 12.3). |

## 3. Results by use case

Result per case: Pass / Fail / Blocked (not executed) / Known-limitation / Info. Where a case ran on more than one setup, each result is listed. IDs in brackets are the report's original IDs where a new case now covers them.

### UC-1 — User Registration

- **Test Case IDs:** TC-REG-01 … TC-UI-03 (11 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-1 User Registration
- **Objective:** Create an account with name, email and password; reject invalid or duplicate data.
- **Environment:** PostgreSQL, SQLite, browser; how run: Real, Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-REG-01** Register with valid data | name 'Reg User', fp.reg.215614030@example.com, valid password | 201, token, role user, no password in body | 201, role user, token present | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 2 | **TC-REG-02** Duplicate email is refused | fp.reg.215614030@example.com again | 400 'An account with this email already exists' | 400 'An account with this email already exists.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 3 | **TC-REG-03** Invalid email format is refused | 'not-an-email', 'a@b' | 422 for both | [422, 422] | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 4 | **TC-REG-04** Empty fields / too-short password are refused | empty name, blank name, empty password, 5-char password, missing email | 422 for every case | {"empty name": 422, "blank name": 422, "empty password": 422, "5-char password": 422, "missing email": 422} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 5 | **TC-REG-05** Email with mixed case and spaces is normalised | ' Fp.MixedCase.215614030@Example.COM ' | stored lower-case without spaces; login works in any case | register 201, stored 'fp.mixedcase.215614030@example.com', login lower 200, upper 200 | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 6 | **TC-REG-06** Over-long name, email and password | name 101 chars, email 260 chars, password 73 bytes, password 72 bytes (limit) | 422 over the limits; 72-byte password accepted | {"name 101 chars": 422, "email 260 chars": 422, "password 73 bytes": 422, "password 72 bytes (limit)": 201} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 7 | **TC-REG-07** Urdu-script name | محمد علی خان | 201; name returned unchanged by /users/me | 201; /users/me name 'محمد علی خان' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 8 | **TC-REG-08** The password never appears in a response, the log or the database | a unique password; register, login, wrong login, duplicate | absent from all 4 response bodies and server.log; stored as a bcrypt hash | found in responses none; in server.log: False; DB value is bcrypt ($2…): True | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 9 | **TC-REG-09** Duplicate-email wording vs the use case | duplicate registration | 'An account with this email already exists' | 'An account with this email already exists.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 10 | **TC-REG-10** Where the app goes after registering | register in the app | use case: login page or home (record) | the backend returns a token at registration (auto sign-in); the screen is recorded in TC-UI-03 | Info (SQLite: Info, PostgreSQL: Info) |
| 11 | **TC-UI-03** Register: mismatch message, then where the app goes (TC-REG-10) | name, new email, password; first a wrong confirmation | a mismatch message; after registering: signed in (home) or the login page | mismatch message shown: True; after registering at '/' (home 'Analyze' visible: True) | Pass |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (10 pass, 0 fail, 0 known limitation, 0 blocked, 1 info)

### UC-2 — Login (and session handling)

- **Test Case IDs:** TC-LOG-01 … TC-UI-15 (20 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-2 Login (and session handling)
- **Objective:** Sign in, keep or end a session safely, lock out password guessing; profile and sign-out screens.
- **Environment:** PostgreSQL, SQLite, browser, real limits; how run: Real, Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-LOG-01** Login with valid credentials | fp.A.215537@example.com | 200 with token and the user's role | 200, role user | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 2 | **TC-LOG-02** Wrong password | fp.A.215537@example.com / wrong password | 401 'Incorrect email or password entered' | 401 'Incorrect email or password entered.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 3 | **TC-LOG-03** Unknown email | nobody@… | 401, same message | 401 'Incorrect email or password entered.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 4 | **TC-LOG-04** Empty fields | empty email/password; empty password; {} | 422 | [422, 422, 422] | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 5 | **TC-LOG-05** Session token works on a protected route | GET /users/me with A's token | 200, A's profile | 200 fp.a.215537@example.com | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 6 | **TC-LOG-06** Password reset | POST /auth/forgot-password etc. | a reset flow | no such endpoint: {'/auth/forgot-password': 404, '/auth/reset-password': 404, '/auth/password-reset': 404} | Known-limitation (SQLite: Known-limitation, PostgreSQL: Known-limitation) |
| 7 | **TC-LOG-07** Wrong password and unknown email give identical errors | TC-LOG-02 vs TC-LOG-03 | same status and message | 401/'Incorrect email or password entered.' vs 401/'Incorrect email or password entered.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 8 | **TC-LOG-08** Lockout after 5 failures and unlock after the window | 5 wrong logins; right password; wait 62 s; right password (server LOGIN_LOCKOUT_MINUTES=1) | 5x 401; 429 even with the right password; 200 after the window | [401, 401, 401, 401, 401]; 429 'Too many failed sign-in attempts. Please try again in 1 minute.' Retry-After 58; after wait 200 | Pass |
| 9 | **TC-LOG-09** Expired token | JWT signed with the server key, exp 5 min ago | 401 | 401 'Could not validate authentication credentials.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 10 | **TC-LOG-10** Tampered JWT signature | A's token with altered signature; token signed by another key; alg=none | 401 for all | {"tampered signature": 401, "wrong key": 401, "alg none": 401} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 11 | **TC-LOG-11** A deleted user's token | register D, submit once, DELETE FROM users (no API for this) | 401 | row deleted; /users/me 401 | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 12 | **TC-LOG-12** Role comes from the database, not the token | same token before/after promote and demote; token claiming role=admin for user A | 403, 200, 403; claim ignored (403) | before 403, promoted 200, demoted 403, admin claim 403 | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 13 | **TC-LOG-13** Logout clears the stored token on web | web app logout | token removed from browser storage | covered in TC-UI (browser) | Info (SQLite: Info, PostgreSQL: Info) |
| 14 | **TC-LOG-14** Spoofed X-Forwarded-For vs the login limiter (TRUST_PROXY_HEADERS off), client from a LAN address (http://192… | 6 wrong logins for one account, each with a different X-Forwarded-For | 5x 401 then 429 | [401, 401, 401, 401, 401, 429] | Pass |
| 15 | **TC-LOG-14-loopback** Spoofed X-Forwarded-For vs the login limiter (TRUST_PROXY_HEADERS off), client from 127.0.0.1 (uvicorn trusts… | 6 wrong logins for one account, each with a different X-Forwarded-For | 5x 401 then 429 | [401, 401, 401, 401, 401, 401] | Info (SQLite: Info, PostgreSQL: Info) |
| 16 | **TC-UI-01** Splash / boot screen, then the sign-in page when signed out | open / signed out | boot screen with the wordmark, then /login | early text ''; now at /login | Pass |
| 17 | **TC-UI-02** Login screen shows the wrong-password message | ui.user.222922@example.com / wrong password | 'Incorrect email or password entered' on screen | on screen: False; dialogs after the click ['Sign in\n\nIncorrect email or password entered.'] | Pass |
| 18 | **TC-UI-04** Forgot password shows 'not available' | open /forgot | message that reset is not available | 'not available' shown: True | Known-limitation |
| 19 | **TC-UI-14** Profile, my profile, edit profile | open each | screens render; edit offers a photo only (no API for profile editing) | edit screen offers photo: True | Pass |
| 20 | **TC-UI-15** Logout clears the stored token on web (TC-LOG-13) | Profile > Sign out | kn_access_token removed; back at /login | token before True; after None; at /login | Pass |

**Comments:** Known limitations: TC-LOG-06, TC-UI-04.  
**Overall result:** PASS with known limitations (16 pass, 0 fail, 2 known limitation, 0 blocked, 2 info)

### UC-3 — Submit Text

- **Test Case IDs:** TC-TXT-01 … TC-UI-09 (48 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-3 Submit Text
- **Objective:** Check Urdu, Roman Urdu, English, mixed and edge-case text with the real models; route, label, score, explanation, history.
- **Environment:** PostgreSQL, SQLite, browser, fault-injected; how run: Fault-injected, Real, Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-TXT-01** Text model missing -> Uncertain, 'unavailable', no score | Urdu sentence with the XLM-R folder pointing at an empty directory | 201; Uncertain; processing_status unavailable; no confidence/risk; no highlights | {"final_label": "Uncertain", "risk": null, "text_conf": null, "model_version": "text-model-unavailable", "processing_status": "unavailable", "analysis_branch": null, "ocr_status": null, "ocr_text": "", "text_prediction": null, "i… | Pass |
| 2 | **TC-TXT-E01 [TC-TXT-05]** english: E01 | The government has announced that all schools will remain closed for a week because of heavy rain. | accepted; route xlmr-roman-urdu; language english; disclosure ['results for English text are less reliable'] | 201; english; xlmr-roman-urdu; Real conf 0.9823 risk 0.0177; 8 highlights; 7.44s | Known-limitation (SQLite: Known-limitation, PostgreSQL: Known-limitation) |
| 3 | **TC-TXT-E02** english: E02 | Scientists have confirmed that drinking hot water with lemon cures every disease within a day. | accepted; route xlmr-roman-urdu; language english; disclosure ['results for English text are less reliable'] | 201; english; xlmr-roman-urdu; Real conf 0.7368 risk 0.2632; 8 highlights; 7.57s | Known-limitation |
| 4 | **TC-TXT-E03** english: E03 | The city council said that the new bus route will start operating from next Monday morning. | accepted; route xlmr-roman-urdu; language english; disclosure ['results for English text are less reliable'] | 201; english; xlmr-roman-urdu; Real conf 0.8521 risk 0.1479; 8 highlights; 6.17s | Known-limitation |
| 5 | **TC-TXT-FI2** Text model throws during inference -> error reported, nothing invented | Roman Urdu sentence; XlmrClassifier.predict raises | 201; Uncertain; no score; summary says the classifier could not complete the check | {"final_label": "Uncertain", "risk": null, "text_conf": null, "model_version": "text-model-unavailable", "processing_status": "unavailable", "analysis_branch": null, "ocr_status": null, "ocr_text": "", "text_prediction": null, "i… | Pass |
| 6 | **TC-TXT-M01** mixed: mostly Urdu letters (>=70%) with English words | حکومت نے نئی ٹیکس پالیسی کا اعلان کیا ہے جس کے تحت online shopping پر اضافی tax لگایا جائے گا۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9682 risk 0.9682; 8 highlights; 0.63s | Pass |
| 7 | **TC-TXT-M02** mixed: Roman Urdu with English | Breaking news: government ne petrol ki price 50 rupees barha di hai, according to sources yeh kal se lagu hogi. | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Fake conf 0.9961 risk 0.9961; 8 highlights; 8.39s | Pass |
| 8 | **TC-TXT-M03** mixed: Urdu script + Roman Urdu, Urdu letters < 50% | حکومت نے اعلان کیا hai ke kal se tamam schools band rahenge aur imtihanat agle mahine honge | accepted; route xlmr-roman-urdu; language mixed; disclosure ['mixes Urdu and English script'] | 201; mixed; xlmr-roman-urdu; Real conf 0.9086 risk 0.0914; 8 highlights; 8.13s | Pass |
| 9 | **TC-TXT-M04** mixed: Urdu with diacritics (zabar/zer/pesh) | حُکُومَت نے اِعلان کِیا ہے کہ اَگلے ہَفتے سے بِجلی کی قِیمَت کَم ہو جائے گی۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Real conf 0.5708 risk 0.4292; 8 highlights; 3.91s | Pass |
| 10 | **TC-TXT-M05** mixed: Urdu (U+06F0) and Arabic-Indic (U+0660) digits | حکومت نے ۱۵ دسمبر سے ۲۰ فیصد سستی بجلی کا اعلان کیا ہے، ٣٠ لاکھ صارفین مستفید ہوں گے۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9998 risk 0.9998; 8 highlights; 1.31s | Pass |
| 11 | **TC-TXT-M06** mixed: Urdu with emoji | 🚨 فوری خبر 🚨 کل سے ملک بھر میں پٹرول پمپ بند رہیں گے 😱🔥 | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Real conf 0.9999 risk 0.0001; 8 highlights; 0.84s | Pass |
| 12 | **TC-TXT-N01** not_news: recipe; use case 3-B expects 'does not appear to be news' | بریانی بنانے کے لیے پہلے چاول بھگو دیں، پھر پیاز سنہری ہونے تک تلیں اور مصالحہ ڈال کر دم پر رکھ دیں۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9998 risk 0.9998; 8 highlights; 0.81s | Pass |
| 13 | **TC-TXT-N02** not_news: greeting; use case 3-B | عید مبارک! آپ کو اور آپ کے پورے خاندان کو دل کی گہرائیوں سے مبارکباد۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Real conf 0.9993 risk 0.0007; 8 highlights; 0.65s | Pass |
| 14 | **TC-TXT-O01** other_language: Arabic: Arabic script; record the route | أعلنت الحكومة اليوم عن إغلاق جميع المدارس لمدة أسبوع بسبب الأمطار الغزيرة في البلاد. | accepted; route None; language None; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.98 risk 0.98; 8 highlights; 1.07s | Pass |
| 15 | **TC-TXT-O02** other_language: Persian: Arabic script; record the route | دولت امروز اعلام کرد که همه مدارس به مدت یک هفته تعطیل خواهند شد. | accepted; route None; language None; disclosure [] | 201; urdu; xlmr-urdu; Real conf 0.9944 risk 0.0056; 8 highlights; 0.61s | Pass |
| 16 | **TC-TXT-O03** other_language: Hindi (Devanagari); record the route | सरकार ने आज घोषणा की कि सभी स्कूल एक हफ्ते के लिए बंद रहेंगे। | accepted; route None; language None; disclosure [] | 201; unknown; xlmr-roman-urdu; Real conf 0.9702 risk 0.0298; 8 highlights; 6.16s | Pass |
| 17 | **TC-TXT-R01 [TC-TXT-04]** roman_urdu: pair of U01 | Hukoomat ne aaj elan kiya hai ke 1 November se tamam sarkari schools mein muft kitaabein faraham ki jayengi. | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Real conf 0.9794 risk 0.0206; 8 highlights; 9.27s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 18 | **TC-TXT-R02** roman_urdu: pair of U02 | Hukoomat ne elan kiya hai ke mulk bhar mein saat din ke liye internet service band kar di jayegi. | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Real conf 0.995 risk 0.005; 8 highlights; 11.52s | Pass |
| 19 | **TC-TXT-R03** roman_urdu: spelling A of one claim | Hukoomat ne petrol ki qeemat mein 20 rupay kami ka elan kar diya hai ke yeh kal se lagu hogi. | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Real conf 0.8236 risk 0.1764; 8 highlights; 9.07s | Pass |
| 20 | **TC-TXT-R04** roman_urdu: spelling B of the same claim | Hakumat ne petrol ki qimat me 20 rupay kami ka elaan kar dia he k yeh kal se lagu hogi. | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Fake conf 0.7524 risk 0.7524; 8 highlights; 8.39s | Pass |
| 21 | **TC-TXT-R05** roman_urdu: spelling C of the same claim | Hkumat ne petrol ki keemat mai 20 rupe kmi ka elan kr diya hai k ye kal se lagu hogi. | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Fake conf 0.9297 risk 0.9297; 8 highlights; 8.62s | Pass |
| 22 | **TC-TXT-R06** roman_urdu: R06 | Social media par khabar phail rahi hai ke kal raat shehar mein zalzala aaya tha lekin mehkama mosamiat ne tasd… (122 ch… | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Fake conf 0.999 risk 0.999; 8 highlights; 12.56s | Pass |
| 23 | **TC-TXT-R07** roman_urdu: credible style | Lahore mein aaj subah halki barish hui aur mosam khushgawar ho gaya, mehkama ne kal bhi barish ka imkan zahir kiya hai. | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Real conf 0.9895 risk 0.0105; 8 highlights; 11.66s | Pass |
| 24 | **TC-TXT-U01 [TC-TXT-02]** urdu_short: given sentence; pair of R01 | حکومت نے آج اعلان کیا ہے کہ یکم نومبر سے تمام سرکاری اسکولوں میں مفت کتابیں فراہم کی جائیں گی۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Real conf 0.9984 risk 0.0016; 8 highlights; 0.55s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 25 | **TC-TXT-U02** urdu_short: given sentence; pair of R02 | حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9994 risk 0.9994; 8 highlights; 0.54s | Pass |
| 26 | **TC-TXT-U03** urdu_short: credible style | شہر میں نئے ہسپتال کی تعمیر کا کام اگلے مہینے مکمل ہو جائے گا۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9944 risk 0.9944; 8 highlights; 0.56s | Pass |
| 27 | **TC-TXT-U04** urdu_short: fake style | سائنسدانوں نے دریافت کیا ہے کہ روزانہ پیاز کھانے سے ہر بیماری ختم ہو جاتی ہے۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9981 risk 0.9981; 8 highlights; 0.54s | Pass |
| 28 | **TC-TXT-U05** urdu_short: fake style | فوری خبر! کل سے ملک کے تمام بینک ایک مہینے کے لیے بند رہیں گے، فوراً اپنی رقم نکال لیں۔ | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9998 risk 0.9998; 8 highlights; 0.58s | Pass |
| 29 | **TC-TXT-UL1 [TC-TXT-03]** urdu_long: 200 words | سوشل میڈیا پر ایک پیغام تیزی سے پھیل رہا ہے جس میں دعویٰ کیا گیا ہے کہ ایک خفیہ دوا ہر بیماری کا علاج کر سکتی … (872 ch… | accepted; route tfidf-urdu-long-articles; language urdu; disclosure ['Long articles are checked as a whole'] | 201; urdu; tfidf-urdu-long-articles; Fake conf 0.7849 risk 0.7849; 8 highlights; 0.84s | Pass |
| 30 | **TC-TXT-UL2** urdu_long: 149 words: just below the cutoff (XLM-R) | شہر کی بلدیہ نے پانی کی فراہمی بہتر بنانے کے لیے ایک نیا منصوبہ شروع کیا ہے۔ منصوبے کے تحت پرانی پائپ لائنوں ک… (695 ch… | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Fake conf 0.9996 risk 0.9996; 8 highlights; 1.67s | Pass |
| 31 | **TC-TXT-UL3** urdu_long: 151 words: just above the cutoff (TF-IDF) | شہر کی بلدیہ نے پانی کی فراہمی بہتر بنانے کے لیے ایک نیا منصوبہ شروع کیا ہے۔ منصوبے کے تحت پرانی پائپ لائنوں ک… (706 ch… | accepted; route tfidf-urdu-long-articles; language urdu; disclosure ['Long articles are checked as a whole'] | 201; urdu; tfidf-urdu-long-articles; Real conf 0.6455 risk 0.3545; 8 highlights; 0.19s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 32 | **TC-TXT-UL4** urdu_long: 145 words but 271 XLM-R tokens after cleaning (limit 256): truncated | سال ۲۰۲۴ میں ۱۲۳۴۵۶۷ روپے کی لاگت سے ۸۹۰۱۲ گھروں کو ۳۴۵۶۷۸ لیٹر پانی ملا۔ رپورٹ نمبر ۵۶۷۸۹۰۱ کے مطابق ۲۳۴۵۶ شک… (758 ch… | accepted; route xlmr-urdu; language urdu; disclosure ['only its first part was checked'] | 201; urdu; xlmr-urdu; Fake conf 0.9428 risk 0.9428; 0 highlights; 0.28s | Pass |
| 33 | **TC-TXT-X01 [TC-TXT-06]** edge: empty |  | rejected_422; route None; language None; disclosure [] | 422; [{'type': 'string_too_short', 'loc': ['body', 'text'], 'msg': 'String should have at least 3 characters', 'input': '', 'ctx': {'min_length': 3}}] | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 34 | **TC-TXT-X02** edge: whitespace only |  | rejected_422; route None; language None; disclosure [] | 422; [{'type': 'value_error', 'loc': ['body', 'text'], 'msg': 'Value error, Text must contain at least 3 non-space characters', 'input': ' \n\t ', 'ctx': {'error': {}}}] | Pass |
| 35 | **TC-TXT-X03** edge: 2 characters, below the 3-character minimum | ab | rejected_422; route None; language None; disclosure [] | 422; [{'type': 'string_too_short', 'loc': ['body', 'text'], 'msg': 'String should have at least 3 characters', 'input': 'ab', 'ctx': {'min_length': 3}}] | Pass |
| 36 | **TC-TXT-X04** edge: exactly 3 characters | خبر | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Real conf 0.9722 risk 0.0278; 1 highlights; 0.06s | Pass |
| 37 | **TC-TXT-X05** edge: exactly 10,000 characters (Roman Urdu, beyond 512 tokens) | Hukoomat ne aaj elan kiya hai ke shehar mein naye bus routes shuru kiye jayenge aur kiraya bhi kam rakha jayeg… (10000 … | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure ['only its first part was checked'] | 201; roman_urdu; xlmr-roman-urdu; Real conf 0.8041 risk 0.1959; 0 highlights; 16.73s | Pass |
| 38 | **TC-TXT-X06** edge: 10,001 characters | Hukoomat ne aaj elan kiya hai ke shehar mein naye bus routes shuru kiye jayenge aur kiraya bhi kam rakha jayeg… (10001 … | rejected_422; route None; language None; disclosure [] | 422; [{'type': 'string_too_long', 'loc': ['body', 'text'], 'msg': 'String should have at most 10000 characters', 'input': 'Hukoomat ne aaj elan kiya hai ke shehar mein naye bus routes shuru kiye jayenge aur kiraya bhi kam rakha j… | Pass |
| 39 | **TC-TXT-X07** edge: emoji only (no letters) | 😀😀😀🎉🎉 | uncertain_no_score; route text-model-unavailable; language None; disclosure [] | 201; unknown; text-model-unavailable; Uncertain conf None risk None; 0 highlights; 0.02s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 40 | **TC-TXT-X08** edge: digits only | 1234567890 | uncertain_no_score; route text-model-unavailable; language None; disclosure [] | 201; unknown; text-model-unavailable; Uncertain conf None risk None; 0 highlights; 0.03s | Pass |
| 41 | **TC-TXT-X09** edge: URL only: the test plan expects Uncertain; the URL does contain letters | https://example.com/news/2026/11/24/story-12345 | uncertain_no_score; route text-model-unavailable; language None; disclosure [] | 201; unknown; xlmr-roman-urdu; Real conf 0.7224 risk 0.2776; 8 highlights; 10.23s | Fail |
| 42 | **TC-TXT-X10** edge: HTML/script tags: must be stored and returned as plain text; tag letters are Latin, so 'mixed' with the… | <script>alert('x')</script><b>حکومت نے</b> آج <i>نئی</i> پالیسی کا اعلان کیا ہے | accepted; route xlmr-urdu; language mixed; disclosure [] | 201; mixed; xlmr-urdu; Real conf 0.9943 risk 0.0057; 8 highlights; 0.67s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 43 | **TC-TXT-X11** edge: zero-width space, non-joiner, joiner and BOM inside the text | حکومت​ نے‌ آج‍ اعلان﻿ کیا ہے کہ کل چھٹی ہوگی | accepted; route xlmr-urdu; language urdu; disclosure [] | 201; urdu; xlmr-urdu; Real conf 0.9999 risk 0.0001; 8 highlights; 0.39s | Pass |
| 44 | **TC-TXT-X12** edge: SQL-injection-style text: stored verbatim, tables unaffected | '; DROP TABLE submissions; -- hukoomat ne elan kiya hai ke kal chutti hogi | accepted; route xlmr-roman-urdu; language roman_urdu; disclosure [] | 201; roman_urdu; xlmr-roman-urdu; Real conf 0.9903 risk 0.0097; 8 highlights; 8.89s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 45 | **TC-UI-05** Home/check: submitting nothing | press Analyze with an empty box | submission blocked (use case wording: 'Please enter news content before submitting') | Analyze aria-disabled='true' (button greyed out, counter 0 / 10,000); no message shown; dialogs []; still on / | Pass |
| 46 | **TC-UI-06** Urdu text check: loading state, result, explanation, right-to-left text | U02 (internet shutdown sentence) | spinner/busy while analysing; result with verdict, score and 'Why this result'; Urdu shown right-to-left; no sideways scroll | while busy: False; result at /result/130; input style {'direction': 'rtl', 'align': 'right', 'font': 'NotoNastaliqUrdu_400Regular'}; result text style {'direction': 'rtl', 'align': 'right', 'font': 'NotoNastaliqUrdu_400Regular', … | Pass |
| 47 | **TC-UI-08** Roman Urdu text check end to end | R02 | result screen with verdict and explanation | reached: Why this result; at /result/131 | Pass |
| 48 | **TC-UI-09** English text: lower-reliability note on screen | E03 | the result says English results are less reliable | note shown: True | Known-limitation |

**Comments:** Failures: TC-TXT-X09 (DEF-01). Known limitations: TC-TXT-E01, TC-TXT-E02, TC-TXT-E03, TC-UI-09.  
**Overall result:** FAIL (43 pass, 1 fail, 4 known limitation, 0 blocked, 0 info)

### UC-4 — Submit Image

- **Test Case IDs:** TC-EVAL-01 … TC-UI-11 (49 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-4 Submit Image
- **Objective:** Upload images; OCR + text classification and AI-or-real detection always run; formats, rejection, evaluation rules.
- **Environment:** PostgreSQL, SQLite, browser, derived, fault-injected; how run: Fault-injected, Manual, Real, Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-EVAL-01** Text verdict plus image output: risk comes from the text only | TC-IMG-C01 | combined_risk_score == text fake probability; image_score separate | risk 0.0001; text fake probability 9.999999999998899e-05; image_score 0.975 | Pass |
| 2 | **TC-EVAL-02** Image without OCR text: Uncertain, no risk, image score present | TC-IMG-C07 | final Uncertain, combined_risk_score None, image_score present | Uncertain, risk None, image_score 0.7886 | Pass |
| 3 | **TC-EVAL-03** OCR text present, image analysis fails | Roman Urdu headline image; detector.analyse raises | text verdict from the OCR text kept; image_score None, image_analysis_status unavailable; no heatmap | {"final_label": "Real", "risk": 0.006, "text_conf": 0.994, "model_version": "img-pair:xlmr-roman-urdu", "processing_status": null, "analysis_branch": "image_pair", "ocr_status": "completed", "ocr_text": "Hukoomat ne mulk bhar mei… | Pass |
| 4 | **TC-EVAL-04** OCR fails, image analysis succeeds | as TC-OCR-FI1 | verdict Uncertain (no text), risk None, image result reported | final Uncertain, risk None, image_score 0.975 | Pass |
| 5 | **TC-EVAL-05** Grad-CAM fails, image analysis succeeds | as TC-GC-FI1 | image result reported, no heatmap; verdict from the OCR text only | final Fake, risk 0.6021, image_score 0.814, gradcam unavailable | Pass |
| 6 | **TC-EVAL-06** Everything available: verdict and risk never averaged with the image score | 13 image-pair results | risk == text fake probability on every one | averaged/mismatched: none | Pass |
| 7 | **TC-EVAL-07** Nothing available (OCR and detector both fail) | English headline image; OCR and detector raise | 201; Uncertain; no risk; no image score; failures stated | {"final_label": "Uncertain", "risk": null, "text_conf": null, "model_version": "image-model-unavailable", "processing_status": null, "analysis_branch": "ai_or_real", "ocr_status": "unavailable", "ocr_text": "", "text_prediction":… | Pass |
| 8 | **TC-EVAL-08** SRS 'weighted combination' of text and image scores | pipeline.evaluate() | document discrepancy with the agreed design | evaluate() takes the verdict and risk only from the text classification; image authenticity is reported separately (the Backend Guide's 70/30 weighting is outdated) | Info |
| 9 | **TC-IMG-C01 [TC-IMG-02]** content: Edge-rendered Urdu headline, black on white, Segoe UI | urdu_headline.png | {"http_status": 201, "analysis_branch": "image_pair", "ocr_status": "completed", "route": "xlmr-urdu"} | 201; branch image_pair; ocr completed conf 0.3938; text Real; final Real risk 0.0001; image_score 0.975 (Likely AI-generated); gradcam completed; 9.58s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 10 | **TC-IMG-C02 [TC-IMG-03]** content: Edge-rendered Roman Urdu headline | roman_headline.png | {"http_status": 201, "analysis_branch": "image_pair", "ocr_status": "completed", "route": "xlmr-roman-urdu"} | 201; branch image_pair; ocr completed conf 0.5427; text Real; final Real risk 0.006; image_score 0.9543 (Likely AI-generated); gradcam completed; 14.59s | Pass |
| 11 | **TC-IMG-C03** content: Edge-rendered English headline | english_headline.png | {"http_status": 201, "analysis_branch": "image_pair", "ocr_status": "completed", "route": "xlmr-roman-urdu", "disclosure": "English"} | 201; branch image_pair; ocr completed conf 0.5957; text Fake; final Fake risk 0.6021; image_score 0.814 (Likely AI-generated); gradcam completed; 10.85s | Pass |
| 12 | **TC-IMG-C04** content: Edge-rendered: one Urdu line and one English line | mixed_scripts.png | {"http_status": 201, "analysis_branch": "image_pair", "ocr_status": "completed"} | 201; branch image_pair; ocr completed conf 0.6945; text Real; final Real risk 0.0002; image_score 0.8282 (Likely AI-generated); gradcam completed; 7.83s | Pass |
| 13 | **TC-IMG-C05** content: Edge-rendered: three numbered Roman Urdu lines (Pehli/Doosri/Teesri) | multiline_paragraph.png | {"http_status": 201, "analysis_branch": "image_pair", "ocr_status": "completed", "reading_order": ["Pehli", "Doosri", "Teesri"]} | 201; branch image_pair; ocr completed conf 0.6434; text Fake; final Fake risk 0.9761; image_score 0.8278 (Likely AI-generated); gradcam completed; 24.91s | Pass |
| 14 | **TC-IMG-C06** content: Edge-rendered light-grey text on grey, Gaussian blur r=2.2 (aims near the OCR cu | low_contrast_blurred.png | {"http_status": 201, "note": "either branch is acceptable; the reason must be consistent with ocr_status/confidence"} | 201; branch ai_or_real; ocr no_text_found conf None; text None; final Uncertain risk None; image_score 0.7498 (Likely AI-generated); gradcam completed; 8.84s | Pass |
| 15 | **TC-IMG-C07 [TC-IMG-01]** content: copy of backend/uploads/393c64a1ecbc4ed380d25eae4c157bde.jpg (fox picture, no te | local_fox_no_text.jpg | {"http_status": 201, "analysis_branch": "ai_or_real", "final_label": "Uncertain", "combined_risk_score": null} | 201; branch ai_or_real; ocr no_text_found conf None; text None; final Uncertain risk None; image_score 0.7886 (Likely AI-generated); gradcam completed; 4.24s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 16 | **TC-IMG-C08** content: local wildebeest photo (watermark strip cut off, 2x) with an Edge-rendered red U | local_photo_caption_bar.jpg | {"http_status": 201, "analysis_branch": "image_pair", "ocr_status": "completed"} | 201; branch image_pair; ocr completed conf 0.7254; text Real; final Real risk 0.0001; image_score 0.5866 (Likely AI-generated); gradcam completed; 7.49s | Pass |
| 17 | **TC-IMG-C09** content: local roses picture with black Roman Urdu meme bars above and below | local_meme.jpg | {"http_status": 201} | 201; branch ai_or_real; ocr completed conf 0.0167; text None; final Uncertain risk None; image_score 0.8676 (Likely AI-generated); gradcam completed; 7.9s | Pass |
| 18 | **TC-IMG-C10** content: generated: gradient with blurred glowing circles (computer-made, no text) | synthetic_render.png | {"http_status": 201, "analysis_branch": "ai_or_real"} | 201; branch ai_or_real; ocr completed conf 0.5486; text None; final Uncertain risk None; image_score 0.8309 (Likely AI-generated); gradcam completed; 6.16s | Pass |
| 19 | **TC-IMG-C11** content: copy of a local picture of roses with an AI-generated look | local_roses_ai_look.jpg | {"http_status": 201, "analysis_branch": "ai_or_real"} | 201; branch ai_or_real; ocr no_text_found conf None; text None; final Uncertain risk None; image_score 0.9837 (Likely AI-generated); gradcam completed; 3.43s | Pass |
| 20 | **TC-IMG-F01** format: English headline saved as JPEG | format_jpeg.jpg | {"http_status": 201} | 201; branch image_pair; ocr completed conf 0.569; text Fake; final Fake risk 0.6021; image_score 0.7483 (Likely AI-generated); gradcam completed; 11.32s | Pass |
| 21 | **TC-IMG-F02** format: English headline saved as PNG | format_png.png | {"http_status": 201} | 201; branch image_pair; ocr completed conf 0.5502; text Fake; final Fake risk 0.6021; image_score 0.8255 (Likely AI-generated); gradcam completed; 10.89s | Pass |
| 22 | **TC-IMG-F03** format: English headline saved as WEBP | format_webp.webp | {"http_status": 201} | 201; branch image_pair; ocr completed conf 0.6724; text Fake; final Fake risk 0.6021; image_score 0.7661 (Likely AI-generated); gradcam completed; 11.23s | Pass |
| 23 | **TC-IMG-F04** format: English headline PNG with alpha 140/255 | format_png_transparent.png | {"http_status": 201} | 201; branch image_pair; ocr completed conf 0.5502; text Fake; final Fake risk 0.6021; image_score 0.8255 (Likely AI-generated); gradcam completed; 11.03s | Pass |
| 24 | **TC-IMG-F05** format: English headline, 8-bit greyscale PNG | format_greyscale.png | {"http_status": 201} | 201; branch image_pair; ocr completed conf 0.5502; text Fake; final Fake risk 0.6021; image_score 0.8255 (Likely AI-generated); gradcam completed; 10.68s | Pass |
| 25 | **TC-IMG-F06** format: 1x1 pixel PNG | format_1x1.png | {"http_status": 201, "note": "accepted; record what the pipeline does"} | 201; branch ai_or_real; ocr no_text_found conf None; text None; final Uncertain risk None; image_score 0.2542 (Likely real photo); gradcam completed; 2.4s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 26 | **TC-IMG-F07** format: 8000x8000 flat PNG (64 Mpx, small file) | format_8000x8000.png | {"http_status": 413, "note": "over MAX_IMAGE_PIXELS (40 Mpx)"} | 413; Image dimensions are too large to analyze. | Pass |
| 27 | **TC-IMG-F07b** format: 6000x6000 flat PNG (36 Mpx, under the pixel cap) | format_6000x6000.png | {"http_status": 201} | 201; branch ai_or_real; ocr no_text_found conf None; text None; final Uncertain risk None; image_score 0.5519 (Likely AI-generated); gradcam completed; 52.82s | Pass |
| 28 | **TC-IMG-F08** format: uncompressed noise PNG just under 10 MiB | format_just_under_10mb.png | {"http_status": 201} | 201; branch ai_or_real; ocr no_text_found conf None; text None; final Uncertain risk None; image_score 0.2109 (Likely real photo); gradcam completed; 23.25s | Pass |
| 29 | **TC-IMG-F09 [TC-IMG-05]** format: uncompressed noise PNG just over 10 MiB | format_just_over_10mb.png | {"http_status": 413} | 413; File is larger than the maximum allowed size of 10 MB. | Pass |
| 30 | **TC-IMG-F10** format: English headline as GIF | format.gif | {"http_status": 415} | 415; Unsupported image format 'gif'. Accepted: JPEG, PNG, WEBP. | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 31 | **TC-IMG-F11** format: English headline as a one-page PDF | format.pdf | {"http_status": 415} | 415; File does not appear to be a valid image. | Pass |
| 32 | **TC-IMG-F12 [TC-IMG-04]** format: a .txt file renamed to .png | text_renamed.png | {"http_status": 415} | 415; File does not appear to be a valid image. | Pass |
| 33 | **TC-IMG-F13** format: the JPEG above cut to half its bytes | truncated.jpg | {"http_status": 415} | 415; File does not appear to be a valid image. | Pass |
| 34 | **TC-IMG-F14 [TC-IMG-06]** format: Urdu headline stored rotated 90 deg CCW with EXIF Orientation=6 (upright when ho | exif_orientation_6.jpg | {"http_status": 201, "ocr_reads_upright": true} | 201; branch image_pair; ocr completed conf 0.3908; text Real; final Real risk 0.0001; image_score 0.9209 (Likely AI-generated); gradcam completed; 8.33s | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 35 | **TC-IMG-F15** format: PNG bytes in a file named .jpg, sent as image/jpeg | png_content_named.jpg | {"http_status": 201, "mime_type": "image/png"} | 201; branch image_pair; ocr completed conf 0.5502; text Fake; final Fake risk 0.6021; image_score 0.8255 (Likely AI-generated); gradcam completed; 11.84s | Pass |
| 36 | **TC-OCR-01** OCR reads Urdu text and sends it to the Urdu model | TC-IMG-C01 | completed; Urdu text; img-pair:xlmr-urdu | ocr_status completed, conf 0.3938, language urdu, branch image_pair, route img-pair:xlmr-urdu, text 'حکومت ے ملک بهر ميں انٹرنیٹ سروس\nکر ديا\nسات دن کے ليے بند کرنے کا\nاعلان' | Pass |
| 37 | **TC-OCR-02** OCR reads Roman Urdu and sends it to the Roman Urdu model | TC-IMG-C02 | completed; Roman Urdu text; img-pair:xlmr-roman-urdu | ocr_status completed, conf 0.5427, language roman_urdu, branch image_pair, route img-pair:xlmr-roman-urdu, text 'Hukoomat ne mulk bhar mein internet\nservice saat din ke liye band karne ka\nelan kar diya' | Pass |
| 38 | **TC-OCR-03** OCR reads English | TC-IMG-C03 | completed; English text; Roman Urdu model with the English note | ocr_status completed, conf 0.5957, language english, branch image_pair, route img-pair:xlmr-roman-urdu, text 'Government announces that all\nschools will remain closed for a week' | Pass |
| 39 | **TC-OCR-04** OCR on mixed Urdu + English | TC-IMG-C04 | completed; both scripts read | ocr_status completed, conf 0.6945, language mixed, branch image_pair, route img-pair:xlmr-urdu, text 'BREAKING: حکومت ے پٹرول كی قیمت ميںكمی\nکر دیا\nکا\nPetrol price cut from tomorrow\nاعلان' | Pass |
| 40 | **TC-OCR-05** No text found is reported as such | TC-IMG-C07 | ocr_status no_text_found (distinct from a failure); ai_or_real branch | ocr_status no_text_found, conf None, language None, branch ai_or_real, route img-ens-clip-dino-r18, text 'None' | Pass |
| 41 | **TC-OCR-06** Low-confidence text: the text verdict is skipped, with the reason | TC-IMG-C06 | below 0.3 or <10 letters -> ai_or_real and the summary says why; otherwise image_pair | ocr_status no_text_found, conf None, language None, branch ai_or_real, route img-ens-clip-dino-r18, text 'None' | Pass |
| 42 | **TC-OCR-07** Multi-line text is read in order | TC-IMG-C05 | Pehli < Doosri < Teesri in ocr_text | ocr_status completed, conf 0.6434, language roman_urdu, branch image_pair, route img-pair:xlmr-roman-urdu, text 'Pehli line: hukoomat ne naya budget pesh kar diya hai\nDoosri line: is mein taleem ke liye ' | Pass |
| 43 | **TC-OCR-08** OCR output is saved and shown in the result and history | TC-HIS-05 | ocr_text/ocr_status in the stored detail | image item 100: ocr_status completed, image_score 0.8255; text preview present True | Pass |
| 44 | **TC-OCR-09** OCR failure is told apart from 'no text found' | TC-OCR-FI1 | a failure status, not no_text_found | ocr_status under an OCR crash: unavailable; without text: no_text_found | Pass |
| 45 | **TC-OCR-10** Windows first run: EasyOCR needs PYTHONUTF8=1 | environment note | documented | EasyOCR's first-run download prints non-ASCII progress; on a cp1252 console it can fail without PYTHONUTF8=1 (the test servers set it). Weights were already cached here. | Info |
| 46 | **TC-OCR-FI1** OCR crashes -> failure reported; image analysis and Grad-CAM still run | Urdu headline image; EasyOCR readtext raises | 201; ocr_status = a failure status (not no_text_found); image_score present; Grad-CAM completed; Uncertain, no risk | {"final_label": "Uncertain", "risk": null, "text_conf": null, "model_version": "img-ens-clip-dino-r18", "processing_status": null, "analysis_branch": "ai_or_real", "ocr_status": "unavailable", "ocr_text": "", "text_prediction": n… | Pass |
| 47 | **TC-UI-10** Image with text: pick, change, analyse; news verdict first, authenticity separate, Grad-CAM caption | roman_headline.png, changed to urdu_headline.png | verdict card first; 'Image authenticity (separate from the verdict above)'; caption names ResNet18; images load | changed picture: False; reached Image authenticity; authenticity heading at char 94; separate-heading True; ResNet18 caption True; loaded <img> 4 | Pass |
| 48 | **TC-UI-10b** Change the picked image (x, then Gallery again) before analysing | roman_headline.png, removed, then urdu_headline.png | the preview clears; the second picture (Urdu) is the one analysed | preview cleared True; result reached Image authenticity; result shows the Urdu headline text True; shows the Roman one False | Pass |
| 49 | **TC-UI-11** Image without text: no verdict invented, authenticity shown | local_fox_no_text.jpg | no fake-news verdict ('No news claim was checked'); authenticity + heatmap | reached Image authenticity; 'no news claim' True; heading 'Image authenticity' True | Pass |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (47 pass, 0 fail, 0 known limitation, 0 blocked, 2 info)

### UC-5 — View Explainability Panel

- **Test Case IDs:** TC-EXP-01 … TC-UI-07 (14 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-5 View Explainability Panel
- **Objective:** Word highlights for text, Grad-CAM heatmaps for images, their captions, privacy and failure handling.
- **Environment:** browser, derived, fault-injected; how run: Fault-injected, Manual, Real, Real (browser), Real (in-process)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-EXP-01** Highlighted words for short XLM-R text | 32 XLM-R results with highlights | 1-8 words from the input, each with a contribution | 32 with highlights; very confident results (>=0.99) whose largest contribution is < 0.01: [('TC-TXT-U02', 0.9994, 0.00044), ('TC-TXT-U03', 0.9944, 0.00665), ('TC-TXT-U04', 0.9981, 0.00199), ('TC-TXT-U05', 0.9998, 4e-05), ('TC-TXT… | Pass |
| 2 | **TC-EXP-02** Grad-CAM heatmap generated for a valid image | TC-IMG-C07 | gradcam completed; PNG served at the upright image size | completed; heatmap [700, 466] vs image [700, 466] | Pass |
| 3 | **TC-EXP-03** Heatmap privacy: another user gets 404 | 21 image submissions | 404 for detail/image/heatmap | non-404: none | Pass |
| 4 | **TC-EXP-04** No highlights when no model ran | TC-TXT-X07 (emoji only) | no highlights; summary says why | highlights []; summary 'The text has no words to classify (only numbers or symbols).' | Pass |
| 5 | **TC-EXP-05** Explanation cannot be produced (use case 4-A) | Urdu sentence; explain_text raises | the classification is still returned with a fallback message ('Detailed explanation is temporarily unavailable') | HTTP 500; {"body": "Internal Server Error"}; rows before 5 after 5 | Fail |
| 6 | **TC-EXP-06** Highlights for long articles (TF-IDF) | TC-TXT-UL1 | words with exact linear-model weights | 8 words: ['استعمال', 'کہنا', 'دوا', 'دیا', 'نقصان', 'کر', 'لوگوں', 'ساتھ'] | Pass |
| 7 | **TC-EXP-07** SRS says SHAP; the code removes one word at a time (XLM-R) / uses linear weights (TF-IDF) | app/ai/text/explain.py | document discrepancy | occlusion over up to 8 words; exact TF-IDF x weight for long articles | Info |
| 8 | **TC-EXP-08** Known weakness: highlights carry almost no weight when confidence is very high | TC-TXT-U02, TC-TXT-U03, TC-TXT-U04, TC-TXT-U05, TC-TXT-UL2, TC-TXT-R06, TC-TXT-M02, TC-TXT-M05, TC-TXT-M06, TC-TXT-N01,… | recorded (audit) | 12 cases: removing any one word changes the score by < 1 point | Known-limitation |
| 9 | **TC-GC-01** A heatmap is made with and without text (OCR and Grad-CAM are not alternatives) | C01 (Urdu text) and C07 (no text) | gradcam completed on both | C01 completed (image_pair); C07 completed (ai_or_real) | Pass |
| 10 | **TC-GC-02** The heatmap explains the class the ensemble shows, on every image | 19 valid images, real detector in-process | gradcam_class == ensemble label for all; include a case where ResNet18 disagrees | class mismatches: none; ResNet18 disagrees with the ensemble on: ['C06', 'C08']; no heatmap on: none | Pass |
| 11 | **TC-GC-03** Flat map: no heatmap when ResNet18 strongly favours the other class (known behaviour) | all valid images | a flat-map case if one occurs | no flat map occurred on this image set (behaviour not observed) | Blocked |
| 12 | **TC-GC-04** Caption says the heatmap is ResNet18-only (not CLIP or DINOv2) | 21 image results with a heatmap | every caption names ResNet18 and excludes the other two | missing on: none | Pass |
| 13 | **TC-GC-FI1** Grad-CAM fails -> 'unavailable', no heatmap invented, image prediction kept | English headline image; the ResNet18 hook is disabled so the backward pass fails | 201; image_score present; gradcam_status unavailable; summary says why; GET /heatmap 404 | {"final_label": "Fake", "risk": 0.6021, "text_conf": 0.6021, "model_version": "img-pair:xlmr-roman-urdu", "processing_status": null, "analysis_branch": "image_pair", "ocr_status": "completed", "ocr_text": "Government announces th… | Pass |
| 14 | **TC-UI-07** Explanation panel shows highlighted words and the plain-language summary | same result | 'Why this result' card with words and summary | card present True; mentions 'AI estimate' True | Pass |

**Comments:** Failures: TC-EXP-05 (DEF-04). Known limitations: TC-EXP-08. Not executed: TC-GC-03 (see section 9).  
**Overall result:** FAIL (10 pass, 1 fail, 1 known limitation, 1 blocked, 1 info)

### UC-6 — Dispute AI Prediction

- **Test Case IDs:** TC-DIS-01 … TC-UI-13 (10 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-6 Dispute AI Prediction
- **Objective:** File a dispute with a justification and optional evidence link; rules and status display.
- **Environment:** PostgreSQL, SQLite, browser; how run: Real, Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-DIS-01** Submit a valid dispute | justification 45 chars + https link | 201, status pending | 201 pending | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 2 | **TC-DIS-02** Empty justification | '' | 422 ('Please provide a justification…') | 422 [{'type': 'string_too_short', 'loc': ['body', 'justification'], 'msg': 'String should have at least 10 characters', 'input': '', 'ctx': {'min_length': 10}}] | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 3 | **TC-DIS-03** Invalid evidence link | 'not a url at all' | 422 ('Please enter a valid URL…') | 422 [{'type': 'value_error', 'loc': ['body', 'evidence_link'], 'msg': 'Value error, Evidence link must be a web link, for example https://geo.tv/news/12345', 'input': 'not a url at all', 'ctx': {'error': | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 4 | **TC-DIS-04** Dispute another user's submission | user B's submission id | 404 | 404 'Submission not found.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 5 | **TC-DIS-05** Justification length limits | 9 chars, 10 spaces+9, exactly 10, 5001 chars, 5000 chars | 9 -> 422, padded 9 -> 422, 10 -> 201, 5000 -> 201, 5001 -> 422 | {"9 chars": 422, "10 spaces+9": 422, "exactly 10": 201, "5001 chars": 422, "5000 chars": 201} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 6 | **TC-DIS-06** Evidence-link rules | blank '', missing, javascript:, data:, ftp:, malformed http://, no dot host, with space, no scheme | blank/missing allowed; javascript:/data:/ftp:/malformed rejected; no scheme -> https:// | {"blank ''": 201, "missing": 201, "javascript:": 422, "data:": 422, "ftp:": 422, "malformed http://": 422, "no dot host": 422, "with space": 422, "no scheme": 201}; 'geo.tv/news/12345' stored as 'https://geo.tv/news/12345'; blank… | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 7 | **TC-DIS-07** Dispute an Uncertain result | submission 109 (digits only -> Uncertain) | 201 | 201 | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 8 | **TC-DIS-08** One pending dispute per submission; a new one allowed after review | dispute twice; admin reviews; dispute again | 409 while pending; 201 after review | while pending 409 'A pending dispute already exists for this submission.'; review 200; after review 201 | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 9 | **TC-DIS-09** Dispute status in history and the user's dispute list | GET /submissions, GET /disputes as A | dispute_count 2 on that submission; first reviewed, second pending | dispute_count 2; statuses reviewed/pending | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 10 | **TC-UI-13** Dispute: short-justification message, submit, then 'waiting for review' | justification 'short', then a full one + 'geo.tv/news/12345' | 'Please write at least 10 characters'; submitted; result shows the dispute as pending | minimum-length hint True ('5 / 10 characters minimum'; use case wording 'Please provide a justification…' not used); dialogs ['Register\n\nPasswords do not match.', 'Dispute sent\n\nAn administrator will review it. Its status is … | Pass |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (10 pass, 0 fail, 0 known limitation, 0 blocked, 0 info)

### UC-7 — View Submission History

- **Test Case IDs:** TC-HIS-01 … TC-UI-12 (8 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-7 View Submission History
- **Objective:** List, page and open own submissions; isolation between users; admin decisions shown.
- **Environment:** PostgreSQL, SQLite, browser; how run: Real, Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-HIS-01** User sees their own history, newest first, with a total | GET /submissions as A | 200, A's items only, X-Total-Count | 200, 9 items, total 9, newest first True | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 2 | **TC-HIS-02** Another user's records are not visible | B lists history; B opens 3 of A's ids | no overlap; 404s | overlap 0; B opening A's ids -> [404, 404, 404] | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 3 | **TC-HIS-03** Empty history | new user | 200 [] total 0 (app: 'You have not submitted any content yet') | 200 [] total 0 | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 4 | **TC-HIS-04** Paging with skip/limit and its limits | limit 0/101/-1, skip -1, limit abc; two pages of 3; skip beyond the end | 422 for invalid values; disjoint pages; [] beyond the end | {"limit=0": 422, "limit=101": 422, "limit=-1": 422, "skip=-1": 422, "limit=abc": 422}; page1 [109, 108, 107]; page2 [106, 105, 104]; beyond [] | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 5 | **TC-HIS-05** Text and image items carry their details | history list + detail of an image item; text preview | list: has_image / text_preview; detail: OCR text, ocr_status, image_score | image item 100: ocr_status completed, image_score 0.8255; text preview present True | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 6 | **TC-HIS-06** Rejected submissions are never saved | 10 rejected text/image inputs from TC-TXT/TC-IMG | none in history | in history: none | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 7 | **TC-HIS-07** Admin override shows in the user's history list | GET /submissions as A after the overrides | final_label + source Admin on the 3 items | {3: ('Fake', 'Admin'), 4: ('Real', 'Admin'), 5: ('Uncertain', 'Admin')} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 8 | **TC-UI-12** History list and its empty state | user with checks; new user | items listed; empty state for a new user ('You have not submitted any content yet') | items show the Urdu check: True; empty state text: 'YOUR ACTIVITY\nHistory\n0 checks saved to your account.\nAll\nMisleading\nUncertain\nCredible\nDisputed\n\ue537\nNo checks yet\nRun your first analysis from the Check tab.\nSta' | Pass |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (8 pass, 0 fail, 0 known limitation, 0 blocked, 0 info)

### UC-8 — Admin Reviews Dispute

- **Test Case IDs:** TC-ADM-03 … TC-UI-19 (9 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-8 Admin Reviews Dispute
- **Objective:** Admin queue, uphold/override with a required comment, the user sees the decision.
- **Environment:** PostgreSQL, SQLite, browser; how run: Real, Real (browser), Real (browser) + screenshot review
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-ADM-03** Admin dispute queue (pending filter) | GET /disputes?status=pending | only pending disputes, from all users | 200; 7 pending; contains A's dispute True | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 2 | **TC-ADM-04** Admin upholds the AI result | uphold_ai + comment | 200; status reviewed; label unchanged | 200 status reviewed | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 3 | **TC-ADM-05** Override to each label; the user sees it as the admin's, with the comment | override to Fake, Real, Uncertain | 200; user's detail: final_label = override, source Admin, admin_comment shown | {"Fake": [200, "Fake", "Admin", "Overridden to Fake by the reviewer."], "Real": [200, "Real", "Admin", "Overridden to Real by the reviewer."], "Uncertain": [200, "Uncertain", "Admin", "Overridden to Uncertain by the reviewer."]} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 4 | **TC-ADM-06** A non-admin gets 403 on every admin route | user A token | 403 everywhere | {"GET /admin/submissions": 403, "GET /admin/stats": 403, "PATCH /disputes/7": 403} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 5 | **TC-ADM-07** A reviewed dispute cannot be reviewed again | PATCH an already reviewed dispute | 409 | 409 'This dispute has already been reviewed.' | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 6 | **TC-ADM-08** Review needs a comment (use case 4-A) | no comment, 2-char comment, whitespace comment, override without label | 422 for each ('Please add a comment…') | {"no comment": [422, "[{'type': 'missing', 'loc': ['body', 'admin_comment'], 'msg': 'Field required', 'input': {"], "2-char comment": [422, "[{'type': 'string_too_short', 'loc': ['body', 'admin_comment'], 'msg': 'String should ha… | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 7 | **TC-UI-16** Admin: dashboard, queue, review (comment required), override, all submissions, moderation tab | dispute 11 from TC-UI-13 | each screen renders; no comment -> 'A comment is required'; override saved | queue lists the dispute: True; no-comment dialog ['Admin review\n\nA comment is required (at least 3 characters).']; dialogs after save ['Admin review\n\nA comment is required (at least 3 characters).', 'Review saved\n\nThe decis… | Pass |
| 8 | **TC-UI-17** The user's result shows the admin's label and comment | the disputed result after the override | final label from the admin, marked as such, with the comment | comment shown True; mentions admin True | Pass |
| 9 | **TC-UI-19** Overridden result: the numbers shown agree with the label shown | the result from TC-UI-17 (AI: Likely misleading 99.9 %, admin override: Credible) | no AI score/risk that contradicts the admin label (or clearly marked as the AI original) | header AI VERDICT (OVERRIDDEN) Likely credible, directly above Score 99.9 % and Fake-news risk 99.9 % (the AI numbers for Misleading) | Fail |

**Comments:** Failures: TC-UI-19 (DEF-02).  
**Overall result:** FAIL (8 pass, 1 fail, 0 known limitation, 0 blocked, 0 info)

### UC-9 — Admin Views All Submissions

- **Test Case IDs:** TC-ADM-01 … TC-ADM-11 (5 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** UC-9 Admin Views All Submissions
- **Objective:** Admin list of every submission, dashboard counts, access to any result.
- **Environment:** PostgreSQL, SQLite; how run: Real
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-ADM-01** Admin lists all submissions | GET /admin/submissions (all pages) | 200; every user's items with the submitter's email | 200; total 123; 7 distinct submitters; A and B present True | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 2 | **TC-ADM-02** Dashboard counts match the database | GET /admin/stats vs SQL counts | identical | API {'users': 22, 'submissions': 123, 'overrides': 3, 'disputes': 9, 'pending': 4}; DB {'users': 22, 'submissions': 123, 'overrides': 3, 'disputes': 9, 'pending': 4} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 3 | **TC-ADM-09** Filtering the all-submissions list (use case promise) | ?final_label=Fake, ?submission_type=image, ?user_email=x | a filter exists | totals {'final_label=Fake': '110', 'submission_type=image': '110', 'user_email=x': '110'} vs unfiltered 110: parameters are ignored (no filter); disputes support ?status= | Fail (SQLite: Fail, PostgreSQL: Fail) |
| 4 | **TC-ADM-10** No submissions recorded yet | GET /admin/submissions on an empty system (captured at setup) | empty list (app: 'No submissions have been recorded yet') | {"status": 200, "items": 0, "total": "0"} | Pass (SQLite: Pass, PostgreSQL: Blocked) |
| 5 | **TC-ADM-11** Admin can open any submission's explanation, image and heatmap | admin opens user I's image submission 80 | 200 x3 | {"detail": 200, "/image": 200, "/heatmap": 200} | Pass (SQLite: Pass, PostgreSQL: Pass) |

**Comments:** Failures: TC-ADM-09 (DEF-03).  
**Overall result:** FAIL (4 pass, 1 fail, 0 known limitation, 0 blocked, 0 info)

### Security and robustness (TC-SEC)

- **Test Case IDs:** TC-SEC-01 … TC-SEC-07 (7 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** Cross-cutting (Security and robustness (TC-SEC))
- **Objective:** Authentication on every route, ownership, path traversal, oversized bodies, CORS, error hygiene, /health.
- **Environment:** PostgreSQL, SQLite; how run: Real
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-SEC-01** Every protected endpoint needs a token | 26 method/path pairs from /openapi.json, no Authorization header | 401 for all | non-401: none | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 2 | **TC-SEC-02** Ownership: user B cannot read another user's data | B opens another user's submission, image, heatmap, dispute | 404 for each; not in B's dispute list | {"submission": 404, "submission/image": 404, "submission/heatmap": 404, "dispute": 404, "dispute (A's list as B)": 0} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 3 | **TC-SEC-03** Path traversal in ids and file names | encoded ../ in ids; huge/negative ids; filename '../../../evil.png' | 404/422 for ids; stored file name is a UUID, original name stripped of folders | {"/submissions/..%2F..%2F.env/image": 404, "/submissions/1%2F..%2F..%2Fapp/heatmap": 404, "/submissions/-1/image": 404, "/submissions/99999999999999999999/image": 500, "/submissions/1;DROP TABLE users/image": 422, "/disputes/..%2… | Fail (SQLite: Fail, PostgreSQL: Fail) |
| 4 | **TC-SEC-04** Oversized request bodies | 1,000,000-character text; 2,000,000-character justification (images: TC-IMG-F09) | 4xx, no crash | {"1M-char text": 422, "2M-char justification": 422} | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 5 | **TC-SEC-05** CORS allows only the configured origins and regex | http://localhost:8082, https://khabarnazar.expo.app, https://khabarnazar--a1b2c3.expo.app, https://evil.example.com, ht… | Allow-Origin echoed only for localhost:8082 and *.expo.app project URLs | {"http://localhost:8082": [200, "http://localhost:8082"], "https://khabarnazar.expo.app": [200, "https://khabarnazar.expo.app"], "https://khabarnazar--a1b2c3.expo.app": [200, "https://khabarnazar--a1b2c3.expo.app"], "https://evil… | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 6 | **TC-SEC-06** No stack traces or secrets in error responses | all recorded response data from this run | none of: Traceback, File ", sqlalchemy, psycopg, full-pass-throwaway-secret-not-used-anywhere-else-0123456789, hashes, local paths | found: none | Pass (SQLite: Pass, PostgreSQL: Pass) |
| 7 | **TC-SEC-07** /health reports the database and models quickly | GET /health | 200; database connected; models block; < 2 s | 200; db {'status': 'connected', 'database': 'sqlite'}; models {'ready': True, 'warmup': 'done', 'models': {'urdu_text': 'loaded', 'roman_urdu_text': 'loaded', 'image_detector': 'loaded', 'ocr': 'loaded'}}; 0.009s | Pass (SQLite: Pass, PostgreSQL: Pass) |

**Comments:** Failures: TC-SEC-03 (DEF-05).  
**Overall result:** FAIL (6 pass, 1 fail, 0 known limitation, 0 blocked, 0 info)

### Rate limit (TC-RL, deploy branch only)

- **Test Case IDs:** TC-RL-01 … TC-RL-03 (3 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** Cross-cutting (Rate limit (TC-RL, deploy branch only))
- **Objective:** Per-user limit on checks with the real 10/min setting.
- **Environment:** real limits; how run: Real
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-RL-01** 11th check within a minute is refused; earlier ones worked | 10 parallel text checks then one more (user R1) | 10x 201, then 429 with Retry-After and a clear message; history 10 | [201, 201, 201, 201, 201, 201, 201, 201, 201, 201]; 11th 429 Retry-After 57 'Too many checks in a short time. Please try again in 57 seconds.'; history 10; 3.7s | Pass |
| 2 | **TC-RL-02** The limit is per user | user R2 right after R1 was limited | 201 | 201 | Pass |
| 3 | **TC-RL-03** Text and image checks share one counter; reads are not limited | R1 (limited) uploads an image; reads history, profile, disputes | image 429; reads 200 | image 429; reads [200, 200, 200] | Pass |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (3 pass, 0 fail, 0 known limitation, 0 blocked, 0 info)

### Database (TC-DB)

- **Test Case IDs:** TC-DB-01 … TC-DB-03 (3 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** Cross-cutting (Database (TC-DB))
- **Objective:** Schema vs documentation; all-or-nothing writes.
- **Environment:** PostgreSQL, fault-injected; how run: Fault-injected, Real
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-DB-01** Schema matches the documentation (scripts/describe_database.py --check) | khabarnazar_test after the PostgreSQL run | docs match the database | Database docs match the database. (also in preflight: alembic check no new operations; head e5b1c7a3d920) | Pass |
| 2 | **TC-DB-02** A submission writes all its rows or none | text + image submission with the Explainability row failing half-way | HTTP 500 (generic), no submission/text/image/explainability rows, no upload or heatmap file left | text 500, image 500; before {'submissions': 9, 'text_submissions': 4, 'image_submissions': 5, 'explainability': 9, 'upload_files': 5, 'heatmaps': 2}; after {'submissions': 9, 'text_submissions': 4, 'image_submissions': 5, 'explai… | Fail |
| 3 | **TC-DB-03** Deleting a user (no API): what happens to their rows | direct SQL DELETE of a user with one submission (TC-LOG-11) | record behaviour | PostgreSQL: {'deleted': 'row deleted', 'orphan_submissions': 0}; SQLite: {'deleted': 'row deleted', 'orphan_submissions': 1} | Info |

**Comments:** Failures: TC-DB-02 (DEF-06).  
**Overall result:** FAIL (1 pass, 1 fail, 0 known limitation, 0 blocked, 1 info)

### App-backend connection (TC-APP)

- **Test Case IDs:** TC-APP-01 … TC-UI-18 (5 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** Cross-cutting (App-backend connection (TC-APP))
- **Objective:** lib/api.ts paths and fields match the backend; timeouts; unreachable backend.
- **Environment:** SQLite, browser; how run: Real, Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-APP-01** Every path used by lib/api.ts exists on the backend | 13 paths parsed from lib/api.ts | all exist under /api/v1 | missing: none; paths ['/admin/stats', '/admin/submissions', '/auth/login', '/auth/register', '/disputes', '/disputes/{id}', '/submissions', '/submissions/image', '/submissions/text', '/submissions/{id}', '/submissions/{id}/heatma… | Pass |
| 2 | **TC-APP-02** ApiSubmission field names match a real response | 18 fields of the ApiSubmission type | every field present in the detail, list-item or admin-item response (the type covers all three) | absent: none | Pass |
| 3 | **TC-APP-03** App analysis timeout is longer than the slowest model call | ANALYSIS_TIMEOUT_MS = 180000 | timeout > slowest measured check | timeout 180s; slowest of 59 checks 52.82s | Pass |
| 4 | **TC-APP-04** Backend unreachable message | fetch fails | 'Cannot reach the backend at …' | message in lib/api.ts: True; on screen: TC-UI-19 | Pass |
| 5 | **TC-UI-18** Backend unreachable message (TC-APP-04) | requests to the API blocked in the browser | 'Cannot reach the backend at …' | dialog ['Could not analyze\n\nCannot reach the backend at http://127.0.0.1:8001. Check the API URL and that FastAPI is running.'] | Pass |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (5 pass, 0 fail, 0 known limitation, 0 blocked, 0 info)

### Navigation and route guard (TC-NAV)

- **Test Case IDs:** TC-NAV-01 … TC-NAV-04 (4 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** Cross-cutting (Navigation and route guard (TC-NAV))
- **Objective:** Deep links, reloads, bad tokens and admin-only routes in the web app.
- **Environment:** browser; how run: Real (browser)
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-NAV-01** Signed out: deep links go to /login; /register stays open | /history, /result/1, /dispute/1, /admin, /profile, /register | /login for all; /register stays | {"/history": "/login", "/result/1": "/login", "/dispute/1": "/login", "/admin": "/login", "/profile": "/login", "/register": "/register"} | Pass |
| 2 | **TC-NAV-02** Valid session: reload keeps the user where they are | reload on /history | still /history | /history | Pass |
| 3 | **TC-NAV-03** Corrupt or expired token at start-up goes to /login | corrupt token; token expired 5 min ago; open /history | /login both times | corrupt -> /login; expired -> /login | Pass |
| 4 | **TC-NAV-04** A non-admin opening /admin goes to the home tab | user opens /admin | redirected to / | / | Pass |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (4 pass, 0 fail, 0 known limitation, 0 blocked, 0 info)

### Performance (TC-PERF)

- **Test Case IDs:** TC-PERF-01 … TC-PERF-03 (2 cases)
- **Test Date:** 2026-11-24
- **Use Case Reference:** Cross-cutting (Performance (TC-PERF))
- **Objective:** Latency, start-up time, memory and concurrent requests (recorded, not failed on CPU latency).
- **Environment:** PostgreSQL, SQLite; how run: Real
- **Assumptions:** real models loaded; synthetic inputs without ground truth; CPU latency is recorded, not failed.
- **Pre-Requisite:** throwaway backend running with migrations at head; test accounts registered (admin via set_user_role.py).

| No. | Test case | Input used | Expected result | Actual result | Result |
|---|---|---|---|---|---|
| 1 | **TC-PERF-01** Latency per route (p50 / max, seconds, first submission of each input) | TC-TXT and TC-IMG results | recorded (CPU) | {"urdu xlmr": {"n": 18, "p50": 0.62, "max": 3.91}, "roman xlmr": {"n": 16, "p50": 8.75, "max": 18.27}, "urdu tfidf": {"n": 2, "p50": 0.52, "max": 0.84}, "image": {"n": 21, "p50": 10.68, "max": 52.82}} | Info (SQLite: Info, PostgreSQL: Info) |
| 2 | **TC-PERF-03** Five simultaneous checks from two users | 5 parallel POST /submissions/text (3 from A, 2 from B) | all 201; each result belongs to its sender and text | wall 12.3s; latencies [1.61, 12.32, 11.53, 1.53, 1.49]; problems none | Pass (SQLite: Pass, PostgreSQL: Pass) |

**Comments:** All cases behaved as expected.  
**Overall result:** PASS (1 pass, 0 fail, 0 known limitation, 0 blocked, 1 info)

## 4. Table 6.10 — Results by use case

| Use case / area | Cases | Passed | Failed | Known limitation | Not executed | Info | Overall |
|---|---|---|---|---|---|---|---|
| UC-1 User Registration | 11 | 10 | 0 | 0 | 0 | 1 | Pass |
| UC-2 Login (and session handling) | 20 | 16 | 0 | 2 | 0 | 2 | Pass |
| UC-3 Submit Text | 48 | 43 | 1 | 4 | 0 | 0 | Fail |
| UC-4 Submit Image | 49 | 47 | 0 | 0 | 0 | 2 | Pass |
| UC-5 View Explainability Panel | 14 | 10 | 1 | 1 | 1 | 1 | Fail |
| UC-6 Dispute AI Prediction | 10 | 10 | 0 | 0 | 0 | 0 | Pass |
| UC-7 View Submission History | 8 | 8 | 0 | 0 | 0 | 0 | Pass |
| UC-8 Admin Reviews Dispute | 9 | 8 | 1 | 0 | 0 | 0 | Fail |
| UC-9 Admin Views All Submissions | 5 | 4 | 1 | 0 | 0 | 0 | Fail |
| SEC Security and robustness (TC-SEC) | 7 | 6 | 1 | 0 | 0 | 0 | Fail |
| RL Rate limit (TC-RL, deploy branch only) | 3 | 3 | 0 | 0 | 0 | 0 | Pass |
| DB Database (TC-DB) | 3 | 1 | 1 | 0 | 0 | 1 | Fail |
| APP App-backend connection (TC-APP) | 5 | 5 | 0 | 0 | 0 | 0 | Pass |
| NAV Navigation and route guard (TC-NAV) | 4 | 4 | 0 | 0 | 0 | 0 | Pass |
| PERF Performance (TC-PERF) | 2 | 1 | 0 | 0 | 0 | 1 | Pass |
| **Total** | **198** | **176** | **6** | **7** | **1** | **8** | |

## 5. Table 6.11 — Test metrics

| Metric | Value | How it is computed |
|---|---|---|
| Test cases designed | 198 | unique IDs (report aliases counted once) |
| Executed | 197 | all except Blocked |
| Passed | 176 | |
| Failed | 6 | |
| Known limitations | 7 | audit limitations 1–5, recorded as such |
| Not executed | 1 | see section 9 |
| Information-only | 8 | records with no pass criterion (latency, design notes) |
| Pass rate | 93.1 % | passed / (executed − info) |
| Defects found | 6 | 0 critical, 0 high, 3 medium, 3 low |
| Defect density | 0.77 defects / KLOC | 6 defects / 7.8 KLOC (non-blank lines in backend/app, app/, lib/, components/) |
| Test case effectiveness | 3.0 % | defects found / cases executed × 100 |
| Previous run (report) | 41 cases, 40 passed, 1 failed (TC-LOG-06) | Roman Urdu mocked; PostgreSQL and app screens not tested |

## 6. Table 6.12 — Requirements traceability matrix

| SRS requirement | Backend / API test cases | App (browser) test cases | Status |
|---|---|---|---|
| FR: User registration (UC-1) | TC-REG-01 … TC-REG-10 (10) | TC-UI-03 | Met |
| FR: Login, session, logout, lockout (UC-2) | TC-LOG-01 … TC-LOG-14-loopback (15) | TC-UI-01, TC-UI-02, TC-UI-04, TC-UI-14, TC-UI-15 | Met |
| FR: Submit text; language detection and routing (UC-3) | TC-TXT-01 … TC-TXT-X12 (44) | TC-UI-05, TC-UI-06, TC-UI-08, TC-UI-09 | Partly met (defect) |
| FR: Submit image; OCR; AI-or-real detection (UC-4) | TC-IMG-C01 … TC-OCR-FI1 (38) | TC-UI-10, TC-UI-10b, TC-UI-11 | Met |
| FR: Evaluation of results (verdict from text only) | TC-EVAL-01, TC-EVAL-02, TC-EVAL-03, TC-EVAL-04, TC-EVAL-05, TC-EVAL-06, TC-EVAL-07, TC-EVAL-08 | — | Met |
| FR: Explainability panel: word highlights, Grad-CAM (UC-5) | TC-EXP-01 … TC-GC-FI1 (13) | TC-UI-07, TC-UI-10, TC-UI-10b | Partly met (defect) |
| FR: Dispute AI prediction (UC-6) | TC-DIS-01 … TC-DIS-09 (9) | TC-UI-13 | Met |
| FR: Submission history (UC-7) | TC-HIS-01, TC-HIS-02, TC-HIS-03, TC-HIS-04, TC-HIS-05, TC-HIS-06, TC-HIS-07 | TC-UI-12 | Met |
| FR: Admin reviews disputes, override (UC-8) | TC-ADM-03, TC-ADM-04, TC-ADM-05, TC-ADM-06, TC-ADM-07, TC-ADM-08 | TC-UI-16, TC-UI-17 | Met |
| FR: Admin views all submissions, dashboard (UC-9) | TC-ADM-01, TC-ADM-02, TC-ADM-09, TC-ADM-10, TC-ADM-11 | — | Partly met (defect) |
| FR: 'Is News?' filter (UC-3 3-B) | TC-TXT-N01, TC-TXT-N02 | — | Not met |
| NFR: Security (authentication, authorisation, input validation) | TC-LOG-08 … TC-SEC-07 (14) | TC-NAV-01, TC-NAV-02, TC-NAV-03, TC-NAV-04 | Partly met (defect) |
| NFR: Abuse protection (rate limits) | TC-RL-01, TC-RL-02, TC-RL-03 | — | Met |
| NFR: Reliability / failure handling | TC-DB-02 … TC-TXT-FI2 (9) | — | Partly met (defect) |
| NFR: Data integrity, schema | TC-DB-01, TC-DB-02, TC-DB-03 | — | Partly met (defect) |
| NFR: Performance | TC-PERF-01, TC-PERF-03 | — | Met |
| NFR: Usability (Urdu right-to-left, layout, messages) | TC-UI-01 … TC-UI-19 (20) | — | Partly met (defect) |
| NFR: Portability (app-backend contract, web) | TC-APP-01, TC-APP-02, TC-APP-03, TC-APP-04 | TC-UI-18 | Met |

## 7. Defect log

| ID | Title | Severity | Steps to reproduce | Expected | Actual | Evidence | Likely file and line | Branches |
|---|---|---|---|---|---|---|---|---|
| DEF-01 | A bare URL (or other non-news Latin text) gets a confident verdict | Medium | POST /api/v1/submissions/text {"text": "https://example.com/news/2026/11/24/story-12345"} | Uncertain with no score (the test plan: no words to classify), or a 'not news' message | 201, detected 'unknown', routed to xlmr-roman-urdu, **Real 72.2 %**, 8 highlighted URL fragments | TC-TXT-X09 | backend/app/ai/text/predict.py:64-74 (model_language: any letters -> classified); language_detection.py | main, deploy |
| DEF-02 | After an admin override, the result still shows the AI's Score and Fake-news risk next to the admin's label | Medium | Text 'حکومت نے اعلان کیا…' (AI: Likely misleading 99.9 %) -> dispute -> admin overrides to Credible -> user opens the result | The admin's label without the AI's numbers, or the numbers clearly labelled as the AI's original estimate | Header 'AI VERDICT (OVERRIDDEN) Likely credible' with **Score 99.9 % / Fake-news risk 99.9 %** directly under it | TC-UI-19 (TC-UI-17); screenshots/UI-17_user_sees_override.png | app/result/[id].tsx:156-164 (HeroStat score/risk always rendered); combined_risk_score kept on override in dispute_service.review_dispute | main, deploy |
| DEF-03 | The admin's all-submissions list cannot be filtered | Medium | GET /api/v1/admin/submissions?final_label=Fake (also ?submission_type=image, ?user_email=…); admin Submissions screen | A filter (use case UC-9) | Parameters ignored (same total 110 for every query); the admin screen has no filter control (History has one) | TC-ADM-09 | backend/app/routers/admin.py:17 (no filter parameters); app/admin/submissions.tsx | main, deploy |
| DEF-04 | If building the text explanation raises, the whole check fails with 500 and the classification is lost | Low | Urdu text with app.ai.pipeline.explain_text raising (fault-injected) | The verdict is still returned with 'Detailed explanation is temporarily unavailable' (use case 4-A) | HTTP 500 'Internal Server Error'; nothing saved. (The model explainers inside explain_text catch their own errors, so this needs a failure outside them.) | TC-EXP-05 | backend/app/ai/pipeline.py:42-49 (run_text_pipeline calls explain_text without a fallback) | main, deploy |
| DEF-05 | A submission id too large for the database returns 500 instead of 404/422 | Low | GET /api/v1/submissions/99999999999999999999/image (also the detail and heatmap routes) | 404 or 422 | 500 Internal Server Error; server log: OverflowError: Python int too large to convert to SQLite INTEGER (PostgreSQL: see TC-SEC-03 PostgreSQL result) | TC-SEC-03 | backend/app/routers/submissions.py:138,154,181 and disputes.py:47,57 (int path ids without bounds) | main, deploy |
| DEF-06 | A failed image submission leaves its heatmap file on disk | Low | Image upload where saving the result fails after the heatmap is rendered (fault-injected) | No rows and no files left | No rows saved and the upload removed (correct), but explanations/<id>_heatmap.png stays (heatmap count 2 -> 3) | TC-DB-02 | backend/app/services/submission_service.py:122-178 (heatmap removed only if db.commit fails, not if an earlier step raises) | main, deploy |

Severity scale: Critical = crash, data loss, cross-user leak or invented result; High = broken workflow; Medium = wrong behaviour with a workaround; Low = cosmetic/robustness.

## 8. Known limitations, findings, design discrepancies and performance

### 8.1 Known limitations (audit items 1–5)

| # | Limitation | Observed in this pass | Presentation correct? |
|---|---|---|---|
| 1 | High AI-generated scores on screenshots/web pictures | C01 98%; C02 95%; C03 81%; C04 83%; C05 83%; C06 75%; C07 79%; C08 59%; C09 87%; C10 83%; C11 98%; F01 75%; F02 83%; F03 77%; F04 83%; F05 83%; F06 25%; F07b 55%; F08 21%; F14 92%; F15 83% | Yes: authenticity is a separate neutral (blue) card, after the text verdict, with the warning that screenshots are often rated AI-generated (TC-UI-10, TC-UI-11) |
| 2 | No heatmap when ResNet18 strongly disagrees | Not triggered by this image set (TC-GC-03 blocked); ResNet18 disagreed with the ensemble on C06 and C08 but still produced a heatmap for the ensemble's class (TC-GC-02) | n/a |
| 3 | CPU latency and memory | p50/max s: urdu xlmr 0.62/3.91; roman xlmr 8.75/18.27; urdu tfidf 0.52/0.84; image 10.68/52.82; peak RAM 6.05 GiB (committed 7.11 GiB) | Yes: app timeout 180 s > slowest check (TC-APP-03) |
| 4 | English goes through the Roman Urdu model | E01–E03 routed to xlmr-roman-urdu; the note is in the summary and on screen | Yes (TC-TXT-E*, TC-UI-09) |
| 5 | No password reset | No endpoint; the Forgot screen says reset is not available | Yes (TC-LOG-06, TC-UI-04) |

### 8.2 Findings that are not failures

- **Urdu vs Roman Urdu pairs:** U01 Real 0.9984 vs R01 Real 0.9794; U02 Fake 0.9994 vs R02 Real 0.995.
- **Three spellings of one Roman Urdu claim:** R03 Real 0.8236; R04 Fake 0.7524; R05 Fake 0.9297.
- **Other languages:** Arabic (O01) and Persian (O02) use Arabic script, so they are read by the **Urdu** model as 'urdu' (Fake 0.98; Real 0.9944); Hindi in Devanagari (O03) is 'unknown' and goes to the Roman Urdu model with 'The language was not clear' (Real 0.9702). Neither is refused.
- **Not news:** a recipe (N01: Fake 0.9998) and an Eid greeting (N02: Real 0.9993) get news verdicts, because no news filter exists (UC-3 3-B).
- **Highlights when very confident:** see TC-EXP-01/08: with confidence ≥ 0.99, removing any single word moves the score by less than one point, so highlights carry little weight (audit note).
- **Truncation:** Urdu over 256 tokens (UL4, 145 words / 271 tokens) and Roman Urdu over 512 tokens (X05) are classified on their first part; the summary says 'only its first part was checked' and word highlights are deliberately left out (explain.py).
- **Grad-CAM class:** `gradcam_class` and the per-model scores are computed but not returned by the API, so TC-GC-02 had to run the detector in-process.
- **Proxy trust in local dev:** uvicorn trusts X-Forwarded-For from 127.0.0.1 by default, so a client on the PC itself can change its login-limiter identity (TC-LOG-14-loopback). Clients on the LAN cannot (TC-LOG-14 passed); on Modal the ASGI app has no uvicorn proxy layer.
- **Deleting a user (no API):** a direct SQL delete — SQLite: {'deleted': 'row deleted', 'orphan_submissions': 1}; PostgreSQL: {'deleted': 'row deleted', 'orphan_submissions': 0} (SQLite does not enforce the ON DELETE CASCADE foreign keys by default; PostgreSQL does). The token stops working either way (TC-LOG-11).

### 8.3 Design documents vs code

| Item | What the report / diagram says | What the code does | Evidence |
|---|---|---|---|
| 'Is News?' filter (Fig 5.2, UC-3 alternative flow 3-B) | Non-news content is refused with 'Submitted content does not appear to be news' | No news classifier is connected; is_news is always None. A recipe and an Eid greeting were classified as news (N01, N02). | TC-TXT-N01, TC-TXT-N02 |
| Notifications module (Fig 5.2) | Users are notified of dispute outcomes | No notifications; the decision is shown on the result screen and in History. | TC-UI-17, TC-HIS-07 |
| Weighted combined risk (SRS; Backend Guide '70/30') | Risk = weighted text + image score | evaluate() uses the text classification only; image authenticity is separate (agreed design). | TC-EVAL-01, TC-EVAL-06 |
| SHAP explanations (SRS) | SHAP values | XLM-R: one word removed at a time (occlusion, up to 8 words); long articles: exact TF-IDF x weight. | TC-EXP-01, TC-EXP-06, TC-EXP-07 |
| Grad-CAM shows 'manipulated regions' | Heatmap of manipulated/edited regions | The detector decides AI-generated vs real photo; Grad-CAM shows ResNet18's evidence for that, from the centre crop only; it does not show edits. | TC-GC-04, screenshots/UI-10* |
| Admins table (ER diagram Fig 4.20) | Separate Admins table | One users table with a role column ('user'/'admin'); admins are made with scripts/set_user_role.py. | TC-LOG-12, SETUP-01 |
| Admin filtering (UC-9) | Admin can filter all submissions | Not implemented (DEF-03); disputes can be filtered by status. | TC-ADM-09, TC-ADM-03 |
| Role-based redirect after login | Each role lands on its own dashboard | Everyone lands on the Check tab; admins reach the Moderation desk from Profile. | TC-UI-03, TC-UI-16 |
| English support | Urdu, Roman Urdu and English classification | No English model: English goes to the Roman Urdu XLM-R with a lower-reliability note (known limitation 4). | TC-TXT-E01..E03, TC-UI-09 |
| Report's 'remaining work' items now done | Listed as future work | Done: Roman Urdu real model (was mocked), PostgreSQL, the app screens, route guards, Grad-CAM, OCR, admin override, rate limits. | TC-TXT-R*, PostgreSQL runs, TC-UI/NAV |
| Profile editing (UC list) | Edit profile details | Only the profile photo (stored on the device); no API for name/email changes. | TC-UI-14 |

**Promised error messages vs actual:**

| Use-case message | Actual | Verdict | Evidence |
|---|---|---|---|
| An account with this email already exists | An account with this email already exists. | Match | TC-REG-09 |
| Incorrect email or password entered | Incorrect email or password entered. | Match | TC-LOG-02, TC-UI-02 |
| Please enter news content before submitting | No message: the Analyze button is disabled until 3 characters are typed (counter 0 / 10,000) | Differs (blocked silently) | TC-UI-05 |
| Submitted content does not appear to be news | Never shown: no news filter | Missing | TC-TXT-N01/N02 |
| Only image manipulation analysis will be performed | 'No readable news text was found in this image, so no news claim was checked.' | Differs (same meaning) | TC-UI-11 |
| Invalid file type. Please upload a valid image | 'Unsupported image format …' / 'File does not appear to be a valid image.' (415) | Differs (same meaning) | TC-IMG-F10..F13 |
| Detailed explanation is temporarily unavailable | Explainer errors: 'The result is available, but its word explanation could not be generated.'; a failure outside them: HTTP 500 (DEF-04) | Differs / defect | TC-EXP-05 |
| Please provide a justification before submitting | '5 / 10 characters minimum' hint under the box; API 422 'Justification must contain at least 10 non-whitespace characters' | Differs | TC-UI-13, TC-DIS-02 |
| Please enter a valid URL for the evidence link | 'Evidence link must be a web link, for example https://geo.tv/news/12345' | Differs (same meaning) | TC-DIS-03, TC-DIS-06 |
| You have not submitted any content yet | 'No checks yet — Run your first analysis from the Check tab.' | Differs (same meaning) | TC-UI-12, TC-HIS-03 |
| Please add a comment before submitting your review | 'A comment is required (at least 3 characters).' | Differs (same meaning) | TC-UI-16, TC-ADM-08 |
| No submissions have been recorded yet | 'No submissions yet' | Differs (same meaning) | TC-ADM-10 |

### 8.4 Performance

| Measure | Value | Evidence |
|---|---|---|
| Latency urdu xlmr (first submission of each input) | n=18, p50 0.62 s, max 3.91 s | TC-PERF-01 |
| Latency roman xlmr (first submission of each input) | n=16, p50 8.75 s, max 18.27 s | TC-PERF-01 |
| Latency urdu tfidf (first submission of each input) | n=2, p50 0.52 s, max 0.84 s | TC-PERF-01 |
| Latency image (first submission of each input) | n=21, p50 10.68 s, max 52.82 s | TC-PERF-01 |
| Start-up (PostgreSQL server, models preloading) | /health answered 2.3 s; all models loaded 50.2 s; first real text check done 52.3 s | postgres/startup.json |
| Memory with all models loaded, after the full bulk run | working set 3.68 GiB, peak 6.05 GiB, committed 7.11 GiB (audit: about 5 GB) | sqlite/ram.json |
| 5 simultaneous checks from 2 users | wall 12.3s; latencies [1.61, 12.32, 11.53, 1.53, 1.49]; problems none | TC-PERF-03 |

## 9. What could not run, and why

- Native app in Expo Go (Android, iPhone): needs a phone; covered by `docs/testing/MANUAL_CHECKLIST.md` (camera roll and HEIC conversion, camera, rotation, network loss, backgrounding).
- TC-GC-03 (flat Grad-CAM map): the behaviour did not occur with this image set, so it could not be observed; it stays a known limitation from the audit.
- Web UI against PostgreSQL and in Safari/iPhone: the browser pass ran once (Edge, phone size) against the SQLite test server; the API groups were repeated on PostgreSQL.
- Text/image on PostgreSQL: a representative subset (8 texts, 5 images) was repeated there; model behaviour does not depend on the database.
- Accuracy metrics: need the labelled test split, which is out of scope for a behaviour pass.
- Notifications and the news filter: not implemented, so there is nothing to execute beyond recording their absence.
- Committing the Phase 2 files before the pass (option A): blocked by the session's permission system; tested as uncommitted changes instead (section 2).

## 10. Re-test after the defect fixes (same day)

The six defects were fixed on the `deploy` branch (not committed yet) and each failing case was run
again with the real models. The tables above stay as the baseline that found them.

| Defect | Fix | Re-test | Result |
|---|---|---|---|
| DEF-01 Bare URL gets a verdict | Links and email addresses are not counted as words (`app/ai/text/predict.py`); a text that is only links is Uncertain with no score | TC-TXT-X09 (real models): Uncertain, no confidence, no risk, no highlights; text with a link plus words is still classified | Pass |
| DEF-02 Overridden result shows the AI's numbers | The result screen leads with "Final verdict (set by an administrator)" and shows the AI's score/risk only as "The AI's original estimate was …"; the risk meter is labelled as the AI's original estimate (`app/result/[id].tsx`, `lib/SubmissionsContext.tsx`) | TC-UI-19 in the browser: screenshots/FIX-DEF-02_overridden_result.png | Pass |
| DEF-03 No admin filter | `GET /admin/submissions` takes `final_label`, `submission_type`, `disputed`, `user_email` (server-side, total matches); the admin screen has All / Misleading / Uncertain / Credible / Disputed / Text / Images chips | TC-ADM-09 (API): filters applied; TC-ADM-09-UI in the browser: screenshots/FIX-DEF-03* | Pass |
| DEF-04 Explanation failure loses the verdict | `run_text_pipeline` keeps the classification and says "Detailed explanation is temporarily unavailable." (`app/ai/pipeline.py`) | TC-EXP-05 (fault-injected, real models): 201, Fake 99.94 %, fallback message | Pass |
| DEF-05 Huge id gives 500 | Path ids are 1 … 2,147,483,647 and `skip` ≤ 2,147,483,647 on every route; the dispute `submission_id` too (`app/utils/dependencies.py` `DbId`) | TC-SEC-03 (real server): 422 instead of 500 | Pass |
| DEF-06 Heatmap file left after a failed image submission | Every step after the heatmap is rendered is inside one cleanup that rolls back and removes the heatmap (`app/services/submission_service.py`) | TC-DB-02 (fault-injected, real models): no rows, no upload, heatmap count unchanged | Pass |

Regression tests: `backend/tests/test_defect_fixes.py` (20 tests). Suites after the fixes:
`pytest` 187 passed / 13 skipped, `pytest --postgres` 187 / 13, `pytest --real-models` 200 passed,
`text_module/tests` 3 passed, `tsc` clean. The rest of the fault-injected cases were re-run too and still pass.

## 11. Manual checklist run in a browser (2026-11-25)

Every step of `MANUAL_CHECKLIST.md` was run by `backend/tests/full_pass/manual_pass.py`. It used
headless Edge at phone size (390×844, touch) on the Expo web app, against a throwaway backend
(SQLite, real models, normal rate limits); the real `khabarnazar` database was not used. Results are in
`backend/tests/full_pass/results_manual_2026-11-25.json`; screenshots are `screenshots/MC-*.png`.

| Result | Steps |
|---|---|
| Pass (real browser) | 1–4, 6–9, 11–14, 17, 18, 20, 23–32 (25) |
| Pass (emulated) | 15 rotation (viewport switched to landscape mid-check), 21 network loss (the upload's connection failed with `ERR_INTERNET_DISCONNECTED` mid-request), 22 backgrounding (page frozen for 20 s) |
| Known limitation | 5 password reset, 10 English reliability note |
| Blocked | 16 iPhone HEIC camera roll, 19 camera: both need a real phone |

No new defects were found. Observations:

- **Start screen on web (step 1).** The branded "News at a Glance" screen covers the session check, so
  the "Loading your session…" text never appears on web. This is expected; the checklist wording is corrected.
- **Whole-browser offline on the dev server (step 21, Info).** When the entire browser goes offline,
  the check still finishes on the server. The app then has to fetch the result screen's code from the
  Expo dev server, which loads screens lazily (`app/result/[id].bundle?lazy=true`), and shows "Something went
  wrong / Failed to fetch". This happens only with `expo start --web`. Expo Go and a built app have the
  screen code already, so they are not affected. With only the backend connection dropped, the app shows
  "Cannot reach the backend at …" and a retry works.
- **Checklist wording fixed in four steps.** Step 13: Analyze stays greyed out below 3 characters (no
  message). Step 17: the picture is changed with the × on the preview (there is no "Change" button).
  Step 20: the exact rejection messages. Step 28: the admin list now has filters (DEF-03 fix).

Still worth repeating on a real phone in Expo Go: steps 15, 16, 19, 21 and 22.

### 11.1 iPhone in Expo Go (2026-11-26)

The project owner ran the app on an iPhone in Expo Go against the local backend. The screenshots are
`screenshots/PHONE-*.jpg`; a personal notification banner was cropped out of one.

| Step | Seen on the phone | Result |
|---|---|---|
| 5 Forgot password | "Password reset is not available yet…" | Known limitation |
| 10 English | "Likely credible" 98.2 %, with the "less reliable" English note | Known limitation |
| 17 Image with text (job poster) | The verdict on the text in the image comes first; "Image authenticity (separate from the verdict above)" follows with the screenshot/poster warning; the Grad-CAM card names ResNet18 and outlines the analysed centre area; the OCR text is shown as the claim | Pass |

Observations (no defects):

- **Blue gear button.** It is Expo Go's developer menu, not part of the app, and is absent from builds.
- **OCR on a styled poster.** EasyOCR misread several words ("LABOR W / RLD", "Pokistan", "yedrs",
  "sdles", "uppointment") and cut "Apply: la" short. These misread words then appear among the
  highlighted words. This is an accuracy limitation.
- **Non-news text gets a verdict.** A job advert still receives a credibility verdict, because any text
  found in an image is checked as a claim. The card says "Verdict on the text in the image". This is a
  design limitation.
- **Poster rated "Likely AI-generated" (90 %).** This is the known screenshot/poster effect, and the app's
  own warning on that card says so.

Steps 15, 16, 19, 21 and 22 on the phone: no results recorded yet.
