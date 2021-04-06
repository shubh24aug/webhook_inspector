from flask import Flask, render_template, url_for, request, redirect
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, desc, join
from sqlalchemy.sql import select
import hashlib
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///webins.db'
db = SQLAlchemy(app)


class Endpoints(db.Model):
    __tablename__ = 'endpoints'
    endpoint_id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(256))
    single_use = db.Column(db.String(3))
    status = db.Column(db.String(8))
    expires_at = db.Column(db.DateTime, default=(datetime.now() + timedelta(hours=1)))
    created_at = db.Column(db.DateTime, default=datetime.now())

    def __repr__(self):
        return '<Endpoint %r>' % self.endpoint_id

class WebhookData(db.Model):
    __tablename__ = 'webhook_data'
    webhook_data_id = db.Column(db.Integer, primary_key=True)
    reference_endpoint = db.Column(db.BigInteger, ForeignKey('endpoints.endpoint_id'))
    hit_at = db.Column(db.DateTime, default=datetime.now())
    header_data = db.Column(db.String)
    form_data = db.Column(db.String)
    raw_data = db.Column(db.String)
    files_data = db.Column(db.String)
    query_params_data = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now())
    
    def __repr__(self):
        return '<WebhookData %r>' % self.webhook_data_id

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/create-endpoint', methods=['GET'])
def create_endpoint():
    try:
        #generating unique endpoint
        unique_endpoint = (hashlib.sha512(str(datetime.now()).encode())).hexdigest()
        
        #new endpoint model, data initialization, adding data, committing data
        new_endpoint = Endpoints(endpoint = unique_endpoint, status = 'Active', single_use = 'No')
        db.session.add(new_endpoint)
        db.session.commit()

        #querying DB to get all the endpoints created
        endpoint = Endpoints.query.order_by(desc(Endpoints.endpoint_id)).all()
        
        # return render_template('show_all_endpoints.html', all_endpoints = endpoint)
        return redirect(url_for('list_endpoints'))

    except Exception as e:
        #rollback if error occurs
        db.session.rollback()

        return render_template('error.html', error = e)


@app.route('/test-webhook/<endpoint>', methods=['GET', 'POST'])
def store_webhook_data(endpoint):

    try:
        if endpoint is not None and endpoint != "" and endpoint != '' and endpoint != ' ':

            query_endpoints = Endpoints.query.where(Endpoints.endpoint==endpoint, Endpoints.status=='Active', Endpoints.expires_at >= datetime.now()).all()

            if len(query_endpoints) == 1:
                request_data = {}

                request_data['query'] = request.args.to_dict() if len(request.args) > 0 else "No Query Parameters."
                request_data['raw_body'] = request.data.decode('utf-8') if len(request.data) > 0 else "No Raw Request Data Found."
                request_data['form_data'] = request.form if len(request.form) > 0 else "No Form Data Found."
                
                form_data = {}
                for key, value in request.form.items():
                    form_data[key] = value

                # extracting Header data
                headers_data = []
                for every_header in str(request.headers).split('\r\n'):
                    headers_data.append(every_header)

                # extracting Files Data : Enhancement- Need to fetch file properties and not the key containing file
                file_data = []
                for files in request.files:
                    file_data.append(files)
                
                #Store the details in the db
                new_webhook_data = WebhookData(
                    reference_endpoint=query_endpoints[0].endpoint_id, 
                    header_data = str(headers_data) if len(headers_data) > 0 else "No Headers Found.", 
                    form_data = str(form_data) if len(form_data) > 0 else "No Form Data Found.", 
                    raw_data = request_data['raw_body'], 
                    files_data = str(file_data) if len(file_data) > 0 else "No Files Found.", 
                    query_params_data = str(request_data['query'])
                )

                db.session.add(new_webhook_data)
                db.session.commit()
                data_posted = {
                    "reference_endpoint" : endpoint, 
                    "header_data"  :  headers_data if headers_data is not None else "No Headers Found.", 
                    "form_data"  :  form_data if len(form_data) > 0 else "No Form Data Found.", 
                    "raw_data"  :  request_data['raw_body'], 
                    "files_data"  :  file_data if len(file_data) > 0 else "No Files Found.", 
                    "query_params_data"  :  request_data['query'],
                    "hit_at" : datetime.now()
                }

                return render_template('show_endpoint_data.html', endpoint = endpoint, data_posted = data_posted, call_from = 'save_data')
            
            else:
                return render_template('error.html', error = "The endpoint is either expired or deleted. Please check and try again.")        
        else:
            return render_template('error.html', error = "Endpoint cannot be empty or none")      
    except Exception as e:
        return render_template('error.html', error = e)


@app.route('/list-endpoints', methods=['GET'])
def list_endpoints():
    try:
        #querying DB to get all the endpoints created
        endpoint = Endpoints.query.order_by(desc(Endpoints.endpoint_id)).all()
        return render_template('show_all_endpoints.html', all_endpoints = endpoint)
    except Exception as e:
        return render_template('error.html', error = e)


@app.route('/endpoint-details/<endpoint>')
def endpoint_details(endpoint):

    try:
        if endpoint is not None and endpoint != "" and endpoint != '' and endpoint != ' ':

            query_endpoints = Endpoints.query.where(Endpoints.endpoint==endpoint, Endpoints.status=='Active', Endpoints.expires_at >= datetime.now()).all()

            if len(query_endpoints) == 1:
                data_posted = WebhookData.query.join(Endpoints, WebhookData.reference_endpoint ==  query_endpoints[0].endpoint_id).order_by(desc(WebhookData.webhook_data_id))
                return render_template('show_endpoint_data.html', data_posted = data_posted, reference_endpoint = endpoint)
            else:
                return render_template('error.html', error = "No Endpoint data found.")
        else:
            return render_template('error.html', error = "Endpoint cannot be blank.")
    except Exception as e:
        return render_template('error.html', error = e)
    


## Code for background process

if __name__ == "__main__":
    app.run(debug=True)


    ''' 
    1. Create Endpoint and store in DB - DONE
    2. Dump data into DB for the endpoint - DONE
    3. Fetch all the endpoints - DONE
    4. Fetch all the data for that endpoint
    5. Background Job
    '''

