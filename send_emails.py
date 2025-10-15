import os
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 설정 파일(config.json) 로드
def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# 이미 보낸 공고 ID 로드 (없으면 빈 set 반환)
def load_sent_jobs():
    if not os.path.exists('sent_jobs.txt'):
        return set()
    with open('sent_jobs.txt', 'r') as f:
        return set(line.strip() for line in f)

# 새로 보낸 공고 ID 저장
def save_sent_jobs(sent_ids):
    with open('sent_jobs.txt', 'w') as f:
        for job_id in sent_ids:
            f.write(str(job_id) + '\n')

# 원티드 API에서 채용 공고 가져오기
def fetch_jobs(config_params):
    # config.json의 파라미터 이름을 Wanted API가 사용하는 이름으로 매핑
    api_params = {
        'locations': config_params.get('locations'),
        'years': config_params.get('years'),
        'job_group_id': config_params.get('job_group_id'),
        'country': 'kr',
        'job_sort': 'job.latest_order',
        'limit': 20
    }
    
    # 값이 없거나 'all'인 파라미터는 제거
    api_params = {k: v for k, v in api_params.items() if v and v != 'all'}
    
    base_url = "https://www.wanted.co.kr/api/v4/jobs"
    try:
        response = requests.get(base_url, params=api_params)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"API 요청 실패: {e}")
        return []

# 이메일 본문 생성
def create_email_body(jobs):
    if not jobs:
        return None

    body = "<h1>✨ 새로운 채용 공고 알림 ✨</h1>"
    body += "<p>설정하신 조건에 맞는 새로운 채용 공고가 등록되었습니다.</p><hr>"
    
    for job in jobs:
        company_name = job.get('company', {}).get('name', '정보 없음')
        position = job.get('position', '정보 없음')
        job_url = f"https://www.wanted.co.kr/wd/{job.get('id')}"
        
        body += f"""
        <div style="margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
            <h3><a href="{job_url}" target="_blank">{position}</a></h3>
            <p><strong>회사:</strong> {company_name}</p>
        </div>
        """
    return body

# 이메일 발송
def send_email(config, body):
    # GitHub Secrets에서 비밀번호를 가져옵니다.
    password = os.getenv(config['smtp_settings']['password_env_var'])
    if not password:
        print("이메일 비밀번호가 설정되지 않았습니다. GitHub Secrets를 확인해주세요.")
        return

    msg = MIMEMultipart()
    msg['From'] = config['smtp_settings']['sender_email']
    msg['To'] = config['email'] # config 최상단에 있는 받는 사람 이메일 주소 사용
    msg['Subject'] = "새로운 원티드 채용 공고 알림"
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    # Override recipient using smtp_settings.receiver_email for consistency with config.json
    msg['To'] = config['smtp_settings']['receiver_email']

    try:
        with smtplib.SMTP(config['smtp_settings']['server'], config['smtp_settings']['port']) as server:
            server.starttls()
            server.login(msg['From'], password)
            server.sendmail(msg['From'], msg['To'], msg.as_string())
        print("이메일 발송 성공!")
    except smtplib.SMTPException as e:
        print(f"이메일 발송 실패: {e}")

def main():
    config = load_config()
    sent_job_ids = load_sent_jobs()
    
    jobs = fetch_jobs(config['search_parameters'])
    
    if not jobs:
        print("API로부터 채용 공고를 가져오지 못했습니다.")
        return

    new_jobs = [job for job in jobs if str(job['id']) not in sent_job_ids]

    if not new_jobs:
        print("새로운 채용 공고가 없습니다.")
        return
        
    print(f"{len(new_jobs)}개의 새로운 공고를 찾았습니다.")
    
    email_body = create_email_body(new_jobs)
    
    if email_body:
        send_email(config, email_body)
        
        new_sent_ids = sent_job_ids.union(str(job['id']) for job in new_jobs)
        save_sent_jobs(new_sent_ids)

if __name__ == "__main__":
    main()
