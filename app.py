from flask import Flask, request, jsonify, render_template
import pandas as pd
import io

app = Flask(__name__)

forecast_data = None


# add route where user can upload a file
@app.route('/upload_forecast', methods=['GET', 'POST'])
def upload_forecast():
    global forecast_data
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'no file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'empty filename'}), 400
        if file:
            try:
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(io.StringIO(file.stream.read().decode('utf-8')), sep=';')
                elif file.filename.endswith('.xlsx'):
                    df = pd.read_excel(io.BytesIO(file.stream.read()))
                else:
                    return jsonify({'error': 'file format not supported'}), 400
                forecast_data = df
                return jsonify({"message": "File successfully uploaded"}), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 400
    elif request.method == 'GET':
        accept_type = request.headers.get('Accept')

        if 'text/html' in accept_type:
            return render_template('planning.html')
        elif 'application/json' in accept_type:
            if forecast_data is not None:
                return forecast_data.to_json(orient='records'), 200
            else:
                return jsonify({'info': 'no file uploaded'}), 200
        else:
            return jsonify({'error': 'accept type not supported'}), 400


@app.route('/')
def home():  # put application's code here
    return render_template('index.html')


@app.route('/planning')
def planning():  # put application's code here
    return render_template('planning.html')


if __name__ == '__main__':
    app.run()
