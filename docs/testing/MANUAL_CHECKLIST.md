# KhabarNazar: manual test checklist (phone and web)

Use this alongside `FULL_TEST_REPORT_2026-11-24.md`. It covers what the automated pass could not:
the native app in Expo Go (Android and iPhone), the camera roll, rotation, network loss and
backgrounding. Fill in the last two columns.

**Before you start**

- Start the backend on the PC with your normal setup (`uvicorn app.main:app --host 0.0.0.0 --port 8000`,
  local PostgreSQL) and wait until `http://<PC-IP>:8000/health` shows `"ready": true` under `models`
  (about a minute after start-up).
- Start the app: `npx expo start`, scan the QR code with Expo Go (phone on the same Wi-Fi).
- Web: `npx expo start --web`, open the printed URL in Chrome (and Safari on iPhone, if you test the web app there).
- Have two accounts ready: a normal user, and an admin (register it, then run
  `.\.venv\Scripts\python.exe scripts\set_user_role.py <email> admin` in `backend/`).
- Copy the images in `backend/tests/full_pass/images/` to the phone (AirDrop, Google Drive, USB or email them to yourself).
- Checks take time on the PC's CPU: Urdu 1–3 s, Roman Urdu up to about 15 s, images 6–15 s. That is not a failure.
- Inputs below come from `backend/tests/full_pass/text_inputs.json` (IDs in brackets).

| # | Area | Do this (exact input) | You should see | Pass/Fail | Notes |
|---|------|------------------------|----------------|-----------|-------|
| 1 | Splash | Open the app signed out. | The KhabarNazar start screen ("Loading your session…"), then the **Welcome back** sign-in page. | | |
| 2 | Register | Tap **Create an account**. Name `Test Phone`, a new email, password `Password123!`, confirm `Password123!x`. Tap **Create account**. | A "Passwords do not match" message; you stay on the form. | | |
| 3 | Register | Fix the confirmation to `Password123!` and tap **Create account**. | You are signed in and land on the **Check** (home) tab. Register the same email again from a signed-out state: "An account with this email already exists." | | |
| 4 | Login | Sign out, then sign in with the right email and password `WrongPass1`. | "Incorrect email or password entered." Same message for an email that does not exist. | | |
| 5 | Forgot password | On sign-in, tap **Forgot password?**, enter your email, tap **Continue**. | A message that password reset is not available yet (known limitation 5). | | |
| 6 | Login | Sign in correctly as the normal user. | The Check tab; no admin tools in Profile. Signing in as the admin shows **Moderation desk**. | | |
| 7 | Empty check | On Check, leave the box empty and tap **Analyze**. | The check does not start; a prompt to enter text (or a disabled button). | | |
| 8 | Urdu text | Paste [U02] `حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔` and tap **Analyze**. | The button shows it is busy while waiting. The result has a **Verdict**, **Score**, **Fake-news risk**, the claim shown **right-to-left in Nastaliq**, "Detected language: Urdu script", and **Why this result** with highlighted Urdu words. | | |
| 9 | Roman Urdu | Paste [R02] `Hukoomat ne elan kiya hai ke mulk bhar mein saat din ke liye internet service band kar di jayegi.` | A Real/Fake verdict with score; highlighted Roman Urdu words; takes up to about 15 s. | | |
| 10 | English | Paste [E01] `The government has announced that all schools will remain closed for a week because of heavy rain.` | A verdict plus the note that results for English text are less reliable (known limitation 4). | | |
| 11 | Long Urdu | Paste [UL1] (the 200-word text in `text_inputs.json`). | A verdict with the note "Long articles are checked as a whole"; highlighted words. | | |
| 12 | Mixed | Paste [M03] `حکومت نے اعلان کیا hai ke kal se tamam schools band rahenge aur imtihanat agle mahine honge` | A verdict and the note that the text mixes scripts and was checked as Roman Urdu. | | |
| 13 | Rejected text | Paste [X03] `ab` and tap **Analyze**. Then paste only spaces. | A clear "too short / enter some text" message; nothing new appears in History. | | |
| 14 | No letters | Paste [X08] `1234567890`. | **Uncertain** with no score and a message that there are no words to classify. | | |
| 15 | Rotate during analysis | Paste [R06] and tap **Analyze**, then rotate the phone while it is busy. | The analysis still finishes and the result opens; nothing is submitted twice (check History). | | |
| 16 | Image from camera roll (iPhone HEIC) | Tap **Gallery**, pick a normal photo you took with the iPhone camera (HEIC). | The picker hands the app a JPEG; the upload is accepted (not "Unsupported image format"). Note what happens if it is refused. | | |
| 17 | Image with text | Pick `urdu_headline.png` (or take a photo of it on a screen), then tap **Change** and pick `roman_headline.png`; tap **Analyze**. | The second picture is the one analysed. The **news verdict comes first**, then **Image authenticity (separate from the verdict above)** in a neutral colour with the screenshot warning, then the Grad-CAM heatmap captioned as coming from the detector's ResNet18 model. | | |
| 18 | Image without text | Pick `local_fox_no_text.jpg`. | No fake-news verdict ("No news claim was checked"), Image authenticity with a percentage, and a heatmap. | | |
| 19 | Camera | Tap **Camera** (phone only), photograph printed or on-screen text. | Permission prompt the first time; the photo is analysed like a gallery image. | | |
| 20 | Rejected image | Pick `format.gif` or the 11 MB `format_just_over_10mb.png`. | "Unsupported image" / "too large" message; nothing new in History. | | |
| 21 | Network loss | Start an image check, then turn on Airplane mode before it finishes. | An error such as "Cannot reach the backend at …" (no crash, no endless spinner). Turn the network back on and retry: it works. | | |
| 22 | Background and return | Start a Roman Urdu check, switch to another app for 20 s, come back. | Either the result is shown or a clear error; the app does not restart or sign you out. | | |
| 23 | History | Open **History**. | Your checks newest first with labels; tap one to open its full result. A brand-new account shows the empty state. | | |
| 24 | Dispute | Open the Urdu result from step 8, tap **Dispute this result**, type `short`, then a real reason and the link `geo.tv/news/12345`; submit. | First "Please write at least 10 characters"; then the dispute is saved, the result shows **Waiting for an administrator to review this dispute**. | | |
| 25 | Admin queue | Sign in as the admin, open **Moderation desk** / admin disputes. | The pending dispute from step 24 is listed. | | |
| 26 | Admin review | Open it, tap **Override verdict** with an empty comment. Then write `Checked with the ministry`, choose **Credible**, tap **Override verdict**. | First "A comment is required (at least 3 characters)"; then "The decision was recorded." | | |
| 27 | User sees decision | Sign back in as the normal user; open the disputed result and History. | Final label **Credible** marked as the admin's decision, with the admin's comment. | | |
| 28 | Admin lists | As admin, open the all-submissions list and the dashboard. | Everyone's checks with their emails; counts on the dashboard. (There is no filter on the list: known gap TC-ADM-09.) | | |
| 29 | Non-admin | As the normal user, open `/admin` on web (type it in the address bar). | You are sent back to the Check tab. | | |
| 30 | Profile | Profile → **My profile**, **Change profile photo** (pick any photo), then **Sign out** → confirm. | Name and email shown; the photo changes locally; after sign-out you are on the sign-in page and Back does not return to protected pages. | | |
| 31 | Session reload (web) | Signed in on web, open History and press F5. Then, signed out, open `/history` directly. | Reload keeps you on History; signed out you are sent to sign-in. | | |
| 32 | Layout | On the phone and in a narrow browser window, scroll the long Urdu result and the image result. | Text wraps, nothing is cut off or scrolls sideways; Urdu stays right-to-left. | | |
