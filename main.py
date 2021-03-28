# Copyright 2019 Google, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START app]
import base64
import json
import logging
import os
import datetime as DT

from flask import current_app, Flask, render_template, request, redirect, url_for
from google.auth.transport import requests
from google.cloud import pubsub_v1
from google.oauth2 import id_token
from google.cloud import storage


app = Flask(__name__)

# Configure the following environment variables via app.yaml
# This is used in the push request handler to verify that the request came from
# pubsub and originated from a trusted source.
app.config['PUBSUB_VERIFICATION_TOKEN'] = \
    os.environ['PUBSUB_VERIFICATION_TOKEN']
app.config['PUBSUB_TOPIC'] = os.environ['PUBSUB_TOPIC']
app.config['PUB_TOPIC'] = os.environ['PUB_TOPIC']
app.config['GOOGLE_CLOUD_PROJECT'] = os.environ['GOOGLE_CLOUD_PROJECT']
app.config['CLOUD_STORAGE_BUCKET'] = os.environ['CLOUD_STORAGE_BUCKET']


gcs = storage.Client()
bucket = gcs.get_bucket(app.config['CLOUD_STORAGE_BUCKET'])
BLOBS = list(gcs.list_blobs(bucket))

# Global list to store messages, tokens, etc. received by this instance.
MESSAGES = []
TOKENS = []
CLAIMS = []

DAYS = []
HOURS =[]
MINUTES = []
SECONDS = []
def getDates():
    today = DT.date.today()
    DAYS.clear()
    for i in range(1,8):
        date = today - DT.timedelta(days=i)
        DAYS.append(str(date))

    for i in range(24):
        if i < 10:
            h = "0" + str(i)
        else:
            h = str(i)
        HOURS.append(h)
            
    for i in range(60):
        if i < 10:
            x = "0" + str(i)
        else:
            x = str(i)
        MINUTES.append(x)
        SECONDS.append(x)


publisher = pubsub_v1.PublisherClient()
# [START index]
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        getDates()
        return render_template('index.html', days=DAYS, hours=HOURS, minutes=MINUTES, seconds=SECONDS)
                           
    day_input = request.form.get('day')
    hr_input = request.form.get('hour')
    min1_input = request.form.get('minute1')
    min2_input = request.form.get('minute2')
    sec1_input = request.form.get('second1')
    sec2_input = request.form.get('second2')

    input = day_input + "-" + hr_input + "-" + min1_input + "_" + sec1_input + "-" + min2_input + "_" + sec2_input
    input = input.encode('utf-8')
    #data = request.form.get('payload', 'Example payload').encode('utf-8')

    # Consider initializing the publisher client outside this function
    # for better latency performance.
    # publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(app.config['GOOGLE_CLOUD_PROJECT'],
                                      app.config['PUB_TOPIC'])
    future = publisher.publish(topic_path, input)
    future.result()
    #MESSAGES.append("another test")
    #return render_template('test.html', messages=MESSAGES, tokens=TOKENS, claims=CLAIMS,blobs=BLOBS, test_message="test msg"), 200
    return redirect(url_for('receive_messages_handler'))
    #return redirect(url_for('download'))
# [END index]
  

# [START push]
@app.route('/push-handlers/receive_messages', methods=['POST', 'GET'])
def receive_messages_handler():
    # Verify that the request originates from the application.
    if (request.args.get('token', '') !=
            current_app.config['PUBSUB_VERIFICATION_TOKEN']):
        return 'Invalid request', 400

    # Verify that the push request originates from Cloud Pub/Sub.
    try:
        # Get the Cloud Pub/Sub-generated JWT in the "Authorization" header.
        bearer_token = request.headers.get('Authorization')
        token = bearer_token.split(' ')[1]
        TOKENS.append(token)

        # Verify and decode the JWT. `verify_oauth2_token` verifies
        # the JWT signature, the `aud` claim, and the `exp` claim.
        # Note: For high volume push requests, it would save some network
        # overhead if you verify the tokens offline by downloading Google's
        # Public Cert and decode them using the `google.auth.jwt` module;
        # caching already seen tokens works best when a large volume of
        # messages have prompted a single push server to handle them, in which
        # case they would all share the same token for a limited time window.
        claim = id_token.verify_oauth2_token(token, requests.Request(),
                                             audience='example.com')
        CLAIMS.append(claim)
    except Exception as e:
        return 'Invalid token: {}\n'.format(e), 400

    envelope = json.loads(request.data.decode('utf-8'))
    payload = base64.b64decode(envelope['message']['data'])
    MESSAGES.append("this is a test")
    MESSAGES.append(payload)
    # Returning any 2xx status indicates successful receipt of the message.
    return render_template('test.html', messages=MESSAGES, tokens=TOKENS,
                               claims=CLAIMS,blobs=BLOBS, test_message="test msg"), 200
    #return "ok", 200
# [END push]


@app.route('/download', methods=['POST','GET'])
def download():
    # Create a Cloud Storage client.
    #gcs = storage.Client()

    # Get the bucket that the file will be uploaded to.
    #bucket = gcs.get_bucket(app.config['CLOUD_STORAGE_BUCKET'])
    #BLOBS = list(gcs.list_blobs(bucket))
    # Create a new blob and upload the file's content.
    blob = bucket.blob('test-data/output2021-03-10T02:45:00.000Z-2021-03-10T02:50:00.000Z-pane-0-last-00-of-01')
    #blob.download_to_file("testfile")
    
    with open('file-to-download-to') as file_obj:
        gcs.download_blob_to_file(blob.public_url, file_obj)  # API request.

    # The public URL can be used to directly access the uploaded file via HTTP.
    #return render_template('test.html', messages=MESSAGES, tokens=TOKENS, claims=CLAIMS, blobs=BLOBS)
    return blob.public_url



@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END app]
