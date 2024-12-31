from flask import Flask, request, jsonify, render_template, redirect, session, url_for
import os
import psycopg2
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your own secret key

# Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_SECRETS_FILE = 'credentials.json'

# Database Connection URL
DATABASE_URL = "postgresql://neondb_owner:Imbnz6G3BANy@ep-summer-lab-a5a8qgzv.us-east-2.aws.neon.tech/neondb?sslmode=require"

# Google OAuth2 Flow
def get_drive_service():
    credentials = Credentials.from_authorized_user_info(session['credentials'], SCOPES)
    return build('drive', 'v3', credentials=credentials)

@app.route('/')
def index():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    return render_template('flask_docx_upload.html')

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = 'https://sample-docuploader.onrender.com/oauth2callback'
    authorization_url, state = flow.authorization_url(include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = 'https://sample-docuploader.onrender.com/oauth2callback'
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
def upload():
    if 'credentials' not in session:
        return jsonify({'success': False, 'message': 'User not authenticated'})

    if 'docx_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request'})
    
    file = request.files['docx_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})

    if file and file.filename.endswith('.docx'):
        # Save file locally
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Upload to Google Drive
        drive_service = get_drive_service()
        file_metadata = {'name': file.filename}
        media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()

        drive_file_id = uploaded_file['id']
        drive_link = uploaded_file['webViewLink']

        # Save record in database
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            tracking_number = f"TRK-{drive_file_id[:8]}"  # Generate a simple tracking number
            cursor.execute(
                """
                INSERT INTO documents (tracking_number, gdrive_location)
                VALUES (%s, %s)
                """,
                (tracking_number, drive_link)
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({'success': False, 'message': f'Database error: {e}'})

        return jsonify({
            'success': True,
            'message': 'File uploaded to Google Drive and saved to database successfully',
            'tracking_number': tracking_number,
            'gdrive_link': drive_link
        })

    return jsonify({'success': False, 'message': 'Invalid file format. Only .docx files are allowed.'})

if __name__ == '__main__':
    app.run(debug=True)
