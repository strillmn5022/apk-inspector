import os
import re
import requests
from flask import Flask, request, render_template_string
from androguard.core.bytecodes.apk import APK

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_TEMPLATE = """
<!doctype html>
<title>APK Info Extractor</title>
<h1>APK 파일 업로드 또는 URL 입력</h1>

<form method=post enctype=multipart/form-data>
  <p>파일 업로드: <input type=file name=apkfile></p>
  <p>또는 구글 드라이브 URL 입력(아직 안됨): <input type=text name=apkurl size=80></p>
  <input type=submit value=분석하기>
</form>

{% if info %}
<h2>추출 결과</h2>
<ul>
  <li><strong>Package:</strong> {{ info['package'] }}</li>
  <li><strong>Version Code:</strong> {{ info['versionCode'] }}</li>
  <li><strong>Version Name:</strong> {{ info['versionName'] }}</li>
  <li><strong>Min SDK Version:</strong> {{ info['minSdkVersion'] }}</li>
  <li><strong>Target SDK Version:</strong> {{ info['targetSdkVersion'] }}</li>
</ul>
{% elif error %}
<p style="color:red;">APK 정보 추출 실패: {{ error }}</p>
{% endif %}
"""

def extract_apk_info(filepath):
    apk = APK(filepath)
    return {
        "package": apk.get_package(),
        "versionCode": apk.get_androidversion_code(),
        "versionName": apk.get_androidversion_name(),
        "minSdkVersion": apk.get_min_sdk_version(),
        "targetSdkVersion": apk.get_target_sdk_version()
    }

def extract_file_id_from_url(url):
    # 다양한 링크 형태 대응
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url) or re.search(r"id=([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None

def convert_to_direct_download_url(gdrive_url):
    file_id = extract_file_id_from_url(gdrive_url)
    if not file_id:
        raise ValueError("Google Drive 링크에서 파일 ID를 추출할 수 없습니다.")
    return f"https://drive.google.com/uc?export=download&id={file_id}", file_id

def download_apk_from_gdrive(url, dest_path):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        print("[DEBUG] Content-Type:", content_type)
        if "text/html" in content_type:
            preview = r.content[:500].decode(errors="ignore")
            print("[DEBUG] Response Preview:", preview)
            raise ValueError("Google Drive에서 APK 파일이 아닌 HTML 페이지를 반환했습니다. 파일이 존재하지 않거나 공유 설정이 잘못되었을 수 있습니다.")
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

@app.route("/", methods=["GET", "POST"])
def upload_or_url():
    info = None
    error = None
    filepath = None

    if request.method == "POST":
        # 1. 파일 업로드 처리
        if 'apkfile' in request.files and request.files['apkfile'].filename.endswith(".apk"):
            file = request.files["apkfile"]
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

        # 2. Google Drive URL 입력 처리
        elif 'apkurl' in request.form and request.form['apkurl'].strip():
            gdrive_url = request.form['apkurl'].strip()
            try:
                download_url, file_id = convert_to_direct_download_url(gdrive_url)
                filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}.apk")
                download_apk_from_gdrive(download_url, filepath)
            except Exception as e:
                error = str(e)

        # 3. APK 분석 시도
        if filepath and not error:
            try:
                info = extract_apk_info(filepath)
            except Exception as e:
                error = f"{e}"
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)

    return render_template_string(HTML_TEMPLATE, info=info, error=error)

if __name__ == "__main__":
    app.run(debug=True)
