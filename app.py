#!/usr/bin/env python3

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import sqlite3
import datetime
import requests
from flask import Flask, request, send_file, make_response
from flask_restx import Api, Resource, fields, reqparse
import json

db_file   = "BerlinTravel.db"
txt_file  = "BerlinTravelGuide.txt"

google_key = os.getenv["GOOGLE_API_KEY"]
if not google_key:
    raise ValueError("Missing GOOGLE_API_KEY environment variable")
    
client = genai.Client(api_key=google_key)

app = Flask(__name__)
api = Api(
    app,
    version='1.0.1',
    title='Berlin Travel API',
    description="Berlin Public Transport Travel Information & Guide API",
)
ns = api.namespace("")

model_stops = api.model('Stop', {
    'stop_id': fields.Integer(example="8000085"),
    'last_updated': fields.String(example="2025-03-08-12:00:40"),
    '_links': fields.Nested(api.model('Links', {
        'self': fields.Nested(api.model('Self', {
            'href': fields.String(example="http://127.0.0.1:5000/stops/8000085")
        }))
    }),)
})

model_stops_200 = api.model('StopError200', {
    'message': fields.String(example="This stop is already in the database.")
})

model_stops_400 = api.model('StopError400', {
    'message': fields.String(example="Your request is not valid.")
})

model_stops_404 = api.model('StopError404', {
    'message': fields.String(example="This stop could not be found, try a different keyword or stop id.")
})

model_stops_503 = api.model('StopError503', {
    'message': fields.String(example="Transport Service is not available now.")
})

@ns.route('/stops')
class ImportStops(Resource):
    @api.response(201, 'Created', model_stops)
    @api.response(200, 'OK', model_stops_200)
    @api.response(400, 'Bad Request', model_stops_400)
    @api.response(404, 'Not Found', model_stops_404)
    @api.response(503, 'Service Unavailable', model_stops_503)  
    @api.param('query', 'Name or keyword of a stop, required')
    def put(self):
        con = sqlite3.connect(db_file)
        c = con.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS stops(stop_id INTEGER PRIMARY KEY, name TEXT, \
                  latitude REAL, longitude REAL, time TEXT, link TEXT, depa TEXT)")

        query = request.args.get('query')
        payload = {'query': query, 'results': '5'}
        r = requests.get('https://v6.vbb.transport.rest/locations', params=payload)
        status = r.status_code  

        try:
            stops = r.json()
        except json.JSONDecodeError:
            if status == 400:
                return {'message': 'Your request is not valid.'}, 400
            if status == 404:
                return {'message': 'This stop could not be found, try a different keyword.'}, 404
            else:
                return {'message': 'Transport Service is not available now.'}, 503

        if not query or status == 400:
            return {'message': 'Your request is not valid.'}, 400
        elif not r or len(stops) == 0 or 'type' not in stops[0] or status == 404:
            return {'message': 'This stop could not be found, try a different keyword.'}, 404
        elif status < 200 or status > 299:
            return {'message': 'Transport Service is not available now.'}, 503
        else:
            output_stops = []
            update_flag = 0
            create_flag = 0
            for i in range(5):
                if stops[i]['type'] == 'stop':
                    stopid = stops[i]['id']
                    res = c.execute(f"SELECT stop_id FROM stops WHERE stop_id='{stopid}'")
                    result1 = res.fetchone()
                    if result1 is not None:
                        time = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
                        c.execute(f"UPDATE stops SET stop_id='{stopid}' WHERE time='{time}'")
                        update_flag = 1
                    else:
                        link = "http://127.0.0.1:5000/stops/" + str(stops[i]['id'])
                        time = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
                        data = (stops[i]['id'], stops[i]['name'], stops[i]['location']['latitude'], \
                                stops[i]['location']['longitude'], time, link)
                        c.execute("INSERT INTO stops (stop_id, name, latitude, longitude, time, link) VALUES(?, ?, ?, ?, ?, ?)", data)
                        con.commit()
                        stop_in = {
                            "stop_id": int(stops[i]['id']),
                            "last_updated": time,
                            "_links": {
                                "self": {
                                    "href": link
                                }
                            }
                        }
                        output_stops.append(stop_in)
                        output_stops.sort(key=lambda x: x['stop_id'])
                        create_flag = 1 
            con.close()              
            if update_flag == 1:
                return {'message': 'This stop is already in the database.'}, 200
            elif create_flag == 1:
                return output_stops, 201

model_thestop = api.model('TheStop', {
    'stop_id': fields.Integer(example="8002549"),
    'last_updated': fields.String(example="2025-03-08-12:00:40"),
    'name': fields.String(example="Hamburg Hbf"),
    'latitude': fields.Float(example="53.553533"),
    'longitude': fields.Float(example="10.00636"),
    'next_departure': fields.String(example="Platform 4 A-C towards Sollstedt"),
    '_links': fields.Nested(api.model('Links2', {
        'self': fields.Nested(api.model('Self2', {
            'href': fields.String(example="http://127.0.0.1:5000/stops/8002549")
        })),
        'next': fields.Nested(api.model('Next', {
            'href': fields.String(example="http://127.0.0.1:5000/stops/8010159")
        })),        
        'prev': fields.Nested(api.model('Prev', {
            'href': fields.String(example="http://127.0.0.1:5000/stops/8000152")
        }))       
    }),)
})

model_delete = api.model('StopDelete', {
    'message': fields.String(example="The stop_id 8010159 has been removed from the database."),
    'stop_id': fields.Integer(example="8010159")
})

model_delete_400 = api.model('StopDelete400', {
    'message': fields.String(example="The stop_id stop8080 is not valid."),
    'stop_id': fields.Integer(example="stop8080")
})

model_delete_404 = api.model('StopDelete404', {
    'message': fields.String(example="The stop_id 8010159 could not be found in the database."),
    'stop_id': fields.Integer(example="8010159")
})

def non_empty_str(value):
    if not value.strip():
        raise ValueError("Cannot be an empty string")
    return value

post = reqparse.RequestParser()
post.add_argument('name', type=non_empty_str, required=False, trim=True, nullable=False, help='A non blank string, optional')
post.add_argument('next_departure', type=non_empty_str, required=False, trim=True, nullable=False, help='A non blank string, optional')
post.add_argument('latitude', type=float, required=False, trim=True, nullable=False, help='A non blank float number, optional')
post.add_argument('longitude', type=float, required=False, trim=True, nullable=False, help='A non blank float number, optional')
post.add_argument('last_updated', type=str, required=False, trim=True, nullable=False, help='A non blank time string, optional')

@ns.route('/stops/<int:stop_id>')
class TheStop(Resource):
    @api.response(200, 'OK', model_thestop)
    @api.response(400, 'Bad Request', model_stops_400)
    @api.response(404, 'Not Found', model_stops_404)
    @api.response(503, 'Service Unavailable', model_stops_503)
    @api.param('include', 'last_updated / name / latitude / longitude / next_departure, optional')
    def get(self, stop_id):
        the_id = stop_id
        intcheck = isinstance(the_id, int)
        if not the_id or not intcheck:
            msg = {
                'message': 'Input stop_id is not valid.'
            }
            return msg, 400  

        include = request.args.get('include')
        if include:
            items = include.split(',')
        else:
            items = []
      
        con = sqlite3.connect(db_file)
        c = con.cursor()  
        res = c.execute(f"SELECT stop_id FROM stops WHERE stop_id='{the_id}'") 
        result = res.fetchone()  

        if result is None:
            return {'message': 'This stop is not in the database.'}, 404
        elif '_links' in items or 'stop_id' in items:
            return {'message': 'Your request is not valid, _links or stop_id is required.'}, 400
        else:
            r = requests.get(f'https://v6.vbb.transport.rest/stops/{the_id}/departures?duration=120')
            status = r.status_code

            if status == 400:
                return {'message': 'Your request is not valid.'}, 400
            elif not r or status == 404:
                return {'message': 'This stop could not be found, try a different stop id.'}, 404
            elif status < 200 or status > 299:
                return {'message': 'Transport Service is not available now.'}, 503
            else:
                depas = r.json()
                if len(depas['departures']) == 0:
                    return {'message': 'This stop has no valid next departure now.'}, 404

                depa = ''
                for i in range(len(depas['departures'])):
                    if depas['departures'][i]['platform'] is not None and depas['departures'][i]['direction'] is not None:
                        platform = str(depas['departures'][i]['platform'])
                        direction = str(depas['departures'][i]['direction'])
                        depa = 'Platform ' + platform + ' towards ' + direction
                        dtime = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
                        break
                
                if not depa:
                    return {'message': 'This stop has no valid next departure now.'}, 404
                else:
                    try:
                        data = (the_id, depa, dtime)
                        c.execute("INSERT INTO stops (stop_id, depa, time) VALUES(?, ?, ?) ON CONFLICT(stop_id) DO UPDATE SET \
                                  depa = excluded.depa, time = excluded.time", data)
                        con.commit()

                        res = c.execute(f"SELECT time, name, latitude, longitude, link FROM stops WHERE stop_id='{the_id}'")
                        time, name, latitude, longitude, self_link = res.fetchone()

                        re1 = c.execute(f"SELECT stop_id FROM stops WHERE stop_id > '{the_id}' ORDER BY stop_id LIMIT 1")
                        result1 = re1.fetchone()
                        if result1 is not None:
                            next = result1[0]
                        else:
                            next = None
                        
                        re2 = c.execute(f"SELECT stop_id FROM stops WHERE stop_id < '{the_id}' ORDER BY stop_id DESC LIMIT 1")
                        result2 = re2.fetchone()
                        if result2 is not None:
                            prev = result2[0]
                        else:
                            prev = None 

                        con.close()
                    except sqlite3.Error:
                        con.close()
                        return {'message': 'Your request could not be found.'}, 404
                    
                    if next is not None:
                        next_link = "http://127.0.0.1:5000/stops/" + str(next)
                    else:
                        next_link = 'This is the last stop, no next stop'

                    if prev is not None:
                        prev_link = "http://127.0.0.1:5000/stops/" + str(prev)
                    else:
                        prev_link = 'This is the first stop, no prev stop.'

                    stop_info = {
                        "stop_id": int(the_id),
                        "last_updated": str(time),
                        "name": str(name),
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                        "next_departure": depa,
                        "_links": {
                            "self": {
                                "href": self_link
                            },
                            "next": {
                                "href": next_link
                            },
                            "prev": {
                                "href": prev_link
                            }
                        } 
                    }
                if not items:
                    return stop_info, 200
                else:
                    include_stop_info = stop_info.copy()
                    if 'last_updated' not in items:
                        del include_stop_info['last_updated']
                    if 'name' not in items:
                        del include_stop_info['name']
                    if 'latitude' not in items:
                        del include_stop_info['latitude']
                    if 'longitude' not in items:
                        del include_stop_info['longitude']
                    if 'next_departure' not in items:
                        del include_stop_info['next_departure']
                    return include_stop_info, 200

    @api.response(200, 'OK', model_delete)
    @api.response(400, 'Bad Request', model_delete_400)
    @api.response(404, 'Not Found', model_delete_404)
    def delete(self, stop_id):
        sid = stop_id
        intcheck = isinstance(sid, int)
        if not sid or not intcheck:
            msg = {
                'message': 'Input stop_id is not valid.'
            }
            return msg, 400
        else:
            con = sqlite3.connect(db_file)
            c = con.cursor()  
            res = c.execute(f"SELECT stop_id FROM stops WHERE stop_id ='{sid}'") 
            result = res.fetchone() 
            if result is None:
                con.close()
                msg = {
                    'message': 'This stop is not in the database.',
                    'stop_id': sid
                }
                return msg, 404
            else:
                res = c.execute(f"DELETE FROM stops WHERE stop_id = '{sid}'")
                con.commit()
                con.close()
                msg = {
                    'message': f'The stop_id {sid} was removed from the database.',
                    'stop_id': sid
                }                
                return msg, 200

    @api.response(200, 'OK', model_stops)
    @api.response(400, 'Bad Request', model_delete_400)
    @api.response(404, 'Not Found', model_delete_404)
    @api.expect(post)
    def patch(self, stop_id):
        sid = stop_id
        intcheck = isinstance(sid, int)
        if not sid or not intcheck:
            msg = {
                'message': 'Input stop_id is not valid.'
            }
            return msg, 400
        else:
            con = sqlite3.connect(db_file)
            c = con.cursor()  
            res = c.execute(f"SELECT stop_id FROM stops WHERE stop_id ='{sid}'") 
            result = res.fetchone() 
            con.close()
            if result is None:
                msg = {
                    'message': 'This stop is not in the database.',
                    'stop_id': sid
                }
                return msg, 404            

        data = post.parse_args(req=request)

        unallowed = ['_links', 'stop_id']
        for field in unallowed:
            if field in request.json:
                msg = {
                    'message': '_links or stop_id is not allowed in the request.',
                    'stop_id': sid
                }                 
                return msg, 400

        allowed = ['name', 'next_departure', 'latitude', 'longitude', 'last_updated']
        allow = 0
        for field in allowed:
            if field in request.json:
                allow = 1

        if allow == 0:
            msg = {
                'message': 'You did not input anything valid to update.',
                'stop_id': sid
            }            
            return msg, 400            

        up_name = data.get('name')
        namecheck = isinstance(up_name, str)
        out_name = None        
        if up_name.strip() and namecheck:
            out_name = up_name
        elif up_name.strip() and not namecheck:
            msg = {
                'message': 'Your update name is invalid.',
                'stop_id': sid
            }            
            return msg, 400

        up_depa = data.get('next_departure')
        depacheck = isinstance(up_depa, str)
        out_depa = None
        if up_depa and depacheck:
            out_depa = up_depa
        elif up_depa and not depacheck:
            msg = {
                'message': 'Your update next_departure is invalid.',
                'stop_id': sid
            }            
            return msg, 400 

        up_la = data.get('latitude')
        lacheck = isinstance(up_la, float)
        out_la = None
        if up_la and lacheck:
            out_la = up_la
        elif up_la and not lacheck:
            msg = {
                'message': 'Your update latitude is invalid.',
                'stop_id': sid
            }            
            return msg, 400

        up_lo = data.get('longitude')
        locheck = isinstance(up_lo, float)
        out_lo = None
        if up_lo and locheck:
            out_lo = up_lo
        elif up_lo and not locheck:
            msg = {
                'message': 'Your update longitude is invalid.',
                'stop_id': sid
            }            
            return msg, 400

        def checktime(time_str):
            try:
                datetime.datetime.strptime(time_str, '%Y-%m-%d-%H:%M:%S')
                return True
            except ValueError:
                return False     

        up_time = data.get('last_updated')
        out_time = None
        if up_time and checktime(up_time):
            out_time = up_time
        elif up_time and not checktime(up_time):
            msg = {
                'message': 'Your update last_updated is invalid.',
                'stop_id': sid
            }            
            return msg, 400
        elif not up_time:
            out_time = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

        con = sqlite3.connect(db_file)
        c = con.cursor()  

        if out_name is not None:
            c.execute(f"UPDATE stops SET name='{out_name}' WHERE stop_id={sid}")
            con.commit()        

        if out_depa is not None:
            c.execute(f"UPDATE stops SET depa='{out_depa}' WHERE stop_id={sid}")
            con.commit()

        if out_la is not None:
            c.execute(f"UPDATE stops SET latitude='{out_la}' WHERE stop_id={sid}")
            con.commit()

        if out_lo is not None:
            c.execute(f"UPDATE stops SET longitude='{out_lo}' WHERE stop_id={sid}")
            con.commit()

        if out_time is not None:
            c.execute(f"UPDATE stops SET time='{out_time}' WHERE stop_id={sid}")
            con.commit()
                                    
        con.close()

        link = "http://127.0.0.1:5000/stops/" + str(sid)
        fmsg = {
            "stop_id": sid,
            "last_updated": out_time,
                "_links": {
                    "self": {
                        "href": link
                        }
                    }
                }
        return fmsg, 200

model_pro = api.model('Profile', {
    'operator_name': fields.String(example="DB Fernverkehr AG"),
    'information': fields.String(example="DB Fernverkehr AG is a subsidiary of Deutsche Bahn that operates long-distance passenger trains in Germany.")
})

model_op = api.model('Operator', {
    'stop_id': fields.Integer(example="8010159"),
    'profiles': fields.List(fields.Nested(model_pro), description='List of operator profiles')
})

@ns.route('/operator-profiles/<int:stop_id>')
class Operators(Resource):
    @api.response(200, 'OK', model_op)
    @api.response(400, 'Bad Request', model_stops_400)
    @api.response(404, 'Not Found', model_stops_404)
    @api.response(503, 'Service Unavailable', model_stops_503)    
    def get(self, stop_id):
        sid = stop_id
        con = sqlite3.connect(db_file)
        c = con.cursor()  
        res = c.execute("SELECT stop_id FROM stops WHERE stop_id='{si}'".format(si=sid)) 
        result = res.fetchone()  
        con.close()

        if result is None:
            return {'message': 'This stop is not in the database.'}, 404        
        else:
            r = requests.get(f'https://v6.vbb.transport.rest/stops/{sid}/departures?duration=90')
            status = r.status_code

            if status == 400:
                return {'message': 'Your request is not valid.'}, 400
            elif not r or status == 404:
                return {'message': 'This stop could not be found, try a different stop id.'}, 404
            elif status < 200 or status > 299:
                return {'message': 'Transport Service is not available now.'}, 503
            else:
                depas = r.json()
                if len(depas['departures']) == 0:
                    return {'message': 'This stop has no valid next departure now.'}, 404

                ops = []
                for i in range(len(depas['departures'])):
                    try:
                        op = depas['departures'][i]['line']['operator']['name']
                    except KeyError:
                        continue
                    if op is not None and op not in ops:
                        ops.append(op)
                    if len(ops) > 4:
                        break
                
                if not ops:
                    return {'message': 'This stop has no valid departure operator now.'}, 404
                else:
                    profs = []
                    for op in ops:
                        try:
                            re = client.models.generate_content(
                                model="gemini-2.0-flash",
                                contents=f"Give me some information about transport operator {op} in no more than 80 words.",
                            )
                        except Exception:
                            return {'message': 'AI Service is not available now.'}, 503

                        info = re.text
                        if not info.strip():
                            return {'message': 'AI Service is not available now.'}, 503

                        prof = {'operator_name': op, 'information': info.strip()}
                        profs.append(prof)

                    response = {'stop_id': sid, 'profiles': profs}
                    return response, 200

model_guide = api.model('Guide', {
    'Web Browser': fields.String(example="We recommend using a web browser for this guide, a Guide.txt file will automatically download for you."),
    'curl': fields.String(example="If you run curl from a terminal, the guide text will be printed on your screen."),
})

@ns.route('/guide')
class Guide(Resource):
    @api.response(200, 'OK', model_guide)
    @api.response(400, 'Bad Request', model_stops_400)
    @api.response(503, 'Service Unavailable', model_stops_503)    
    def get(self):
        con = sqlite3.connect(db_file)
        c = con.cursor()
        c.execute("SELECT name FROM stops")
        results = c.fetchall()
        stops = '; '.join([row[0] for row in results])
        c.close()
        con.close()  

        if len(results) < 2:
            return {'message': 'You have not put enough stops for a guide.'}, 400

        try:
            re = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"Here are some European stops: {stops}. Choose any 2 of them, one as start and the other as destination, use Google map to check if there is a public transport line between them, choose 1 and give a detailed introduction, include all information that would be useful for a tourist, like time, price, service, food&drinks, air conditioner, pets, toliets, smoking, wifi; you must include at least 1 point of interests for both start and destination, introduce each point in 200 words including address, opening time, ticket price, food&drinks, recommendation, anecdote. If there is no public transport line between any 2 stops I provide or there is any other problem that you cannot complete this task, just answer me NOTFOUND.",
            )
        except Exception:
            return {'message': 'AI Service is not available now.'}, 503

        guide = re.text
        if 'NOTFOUND' in guide or not guide:
            return {'message': 'Oops, we cannot provide a guide for your stops.'}, 400

        with open(txt_file, 'w') as f:
            f.write(guide)

        response = make_response(send_file(txt_file, as_attachment=True, download_name='Guide.txt'))
        response.status_code = 200
        return response

if __name__ == '__main__':
    app.run(debug=False)
