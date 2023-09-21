from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint
import pandas as pd
import io
from datetime import datetime


def format_date(value, format='%Y-%m-%d'):
    if isinstance(value, str):
        value = datetime.strptime(value, '%Y-%m-%d')
    return value.strftime(format)

def week_day(value):
    if isinstance(value, str):
        value = datetime.strptime(value, '%Y-%m-%d')
    return value.strftime('%A')


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.debug = True
app.jinja_env.filters['format_date'] = format_date
app.jinja_env.filters['week_day'] = week_day


db = SQLAlchemy(app)



class Forecast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    upload_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    forecast_date = db.Column(db.DateTime, nullable=False)
    forecast_qty = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'{self.forecast_date.date()} - {self.forecast_qty}'
    

class PlanParameters(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    picking_capacity = db.Column(db.Integer, nullable=False,
                                 info={CheckConstraint('picking_capacity >= 0')})
    packing_capacity = db.Column(db.Integer, nullable=False,
                                 info={CheckConstraint('packing_capacity >= 0')})
    forecast_addition = db.Column(db.Integer, nullable=True, 
                                  info={CheckConstraint('forecast_addition >= -100 AND forecast_addition <= 100')})
    work_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    

with app.app_context():
    db.create_all()

# add route where user can upload a file
@app.route('/upload_forecast', methods=['POST'])
def upload_forecast():

    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'no file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'empty filename'}), 400
        if file:
            try:
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(io.StringIO(file.stream.read().decode('utf-8')), sep=';', decimal=',')
                elif file.filename.endswith('.xlsx'):
                    df = pd.read_excel(io.BytesIO(file.stream.read()))
                else:
                    return jsonify({'error': 'file format not supported'}), 400
                
                df.columns = ['forecast_date', 'forecast_qty']
                df['forecast_date'] = pd.to_datetime(df['forecast_date'], format='%d/%m/%Y')

                df['forecast_qty'] = df['forecast_qty'].astype('double').round(0).astype(int)
                for index, row in df.iterrows():
                    forecast = Forecast(forecast_date=row['forecast_date'], forecast_qty=row['forecast_qty'])
                    db.session.add(forecast)
                db.session.commit()


                return redirect('/planning')
            except Exception as e:
                return jsonify({'error': str(e)}), 400
    else:
        return jsonify({'error': 'method not allowed'}), 405


@app.route('/update_parameters', methods=['POST'])
def update_parameters():

    if request.method == 'POST':
        picking_capacity = int(request.form.get('picking-cap'))
        packing_capacity = int(request.form.get('packing-cap'))
        additional_to_forecast = int(request.form.get('forecast-add'))
        print(picking_capacity, packing_capacity, additional_to_forecast)
        if not picking_capacity or not packing_capacity:
            return jsonify({'error': 'missing parameters'}), 400
        if picking_capacity < 0 or packing_capacity <0 or additional_to_forecast < -100 or additional_to_forecast > 100:
            return jsonify({'error': 'invalid parameters'}), 400
        try:
            latest_upload_date = db.session.query(db.func.max(Forecast.upload_date))
            forecast = Forecast.query.filter(Forecast.upload_date==latest_upload_date)
            forecast = forecast.filter(Forecast.forecast_date >= datetime.today().date())

            for f in forecast:
                if f.forecast_date.weekday() < 5:
                    daily_picking_capacity = picking_capacity
                    daily_packing_capacity = packing_capacity
                else:
                    daily_picking_capacity = 0
                    daily_packing_capacity = 0

                parameter_row = PlanParameters.query.filter(PlanParameters.work_date==f.forecast_date).first()
                if parameter_row:
                    parameter_row.picking_capacity = daily_picking_capacity
                    parameter_row.packing_capacity = daily_packing_capacity
                    parameter_row.forecast_addition = additional_to_forecast
                else:
                    parameter = PlanParameters(work_date=f.forecast_date,
                                                picking_capacity=daily_picking_capacity,
                                                  packing_capacity=daily_packing_capacity,
                                                    forecast_addition=additional_to_forecast)
                    db.session.add(parameter)
            db.session.commit()

            return redirect('/planning')
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    else:
        return jsonify({'error': 'method not allowed'}), 405
    

@app.route('/')
def home():  
    return render_template('index.html')


@app.route('/planning')
def planning():
    # returning planning page with data table filled
    # based on the leatest forecast and parameters
    latest_upload_date = db.session.query(db.func.max(Forecast.upload_date))
    planning_parameters = PlanParameters.query.first()
    planning_data = db.session().query(
        Forecast.forecast_date, Forecast.forecast_qty, PlanParameters.picking_capacity,
          PlanParameters.packing_capacity, PlanParameters.forecast_addition, PlanParameters.id.label('parameter_id')
          ).outerjoin(
              PlanParameters, Forecast.forecast_date==PlanParameters.work_date
              ).filter(
                  Forecast.upload_date==latest_upload_date
                  ).filter(
                      Forecast.forecast_date >= datetime.today().date()
                      ).all()
    return render_template(
        'planning.html',
        forecasts=planning_data,
        today=datetime.today(), 
        latest_forecast_upload=latest_upload_date[0][0],
        planning_parameters=planning_parameters
        )


if __name__ == '__main__':
    app.run()
