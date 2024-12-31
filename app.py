from flask import Flask, request, jsonify, render_template, redirect, session, url_for
import os
import io
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
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    authorization_url, state = flow.authorization_url(include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)
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
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Upload to Google Drive
        drive_service = get_drive_service()
        file_metadata = {'name': file.filename}
        media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        return jsonify({'success': True, 'message': 'File uploaded to Google Drive successfully'})

    return jsonify({'success': False, 'message': 'Invalid file format. Only .docx files are allowed.'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

