#!/usr/bin/env python

from flask import Flask, request, json, jsonify
import requests
from datetime import datetime
import sys
import logging
from logging.handlers import RotatingFileHandler
from logging import Formatter

#config_file = '/etc/eliot/config.json'
config_file = './config/config.json'
#extractor_file = '/etc/eliot/extractor.json'
extractor_file = './config/extractor.json'

app = Flask(__name__)


@app.route("/eliot/services/internal/payload/extract/<type>")
def _extract_payload(type):
    '''
    REST API transforming eliot device payload into json object
    type => type of payload:
        - universal: standard eliot payload
        - sigfox: payload optimized for sigfox communication
    arguments:
        - id: id of the device
        - code: device type (optionnal)
        - payload: hexadecimal representation of the payload
    '''
    result = {}
    try:
        id = request.args.get('id')
        result['id'] = id
        result['time'] = datetime.utcnow()
        code = request.args.get('code')
        hex = request.args.get('payload')
        data = {}
        result['data'] = data
        if hex is not None and len(hex) > 16:
            r = _extract_data(type, code, hex, data)
        if r == 1:
            result['code'] = 200
            result['msg'] = 'Data succesfully loaded for device {}'\
                            ''.format(id)
        elif r == -1:
            result['code'] = 404
            result['msg'] = '{} is not a valid type'.format(type)
        elif r == 0:
            result['code'] = 400
            result['msg'] = 'Error in parameters'
    except Exception as e:
        result['code'] = 500
        result['msg'] = 'Error loading values: {}'.format(str(e.args))
    return jsonify(result)


#load parser, extract data and load in data
def _extract_data(type, code, hex, data):
    extractor = _extractor_description()
    ext_type = extractor.get(type)
    if ext_type is not None:
        if type == "universal" or type == "sigfox":
            return _extract_payload(ext_type, hex, data)
        else:
            return -1


#extract data from payload
def _extract_payload(ext_type, hex, data):
    codes = ext_type.get('codes')
    r = _extract_values(codes, hex, data)
    if r == 1:
        sensor_code = data.get('sensor_code')
        sensor_desc = ext_type.get('sensors').get(sensor_code)
        if sensor_desc is not None:
            data['name'] = sensor_desc.get('name')
            l = ext_type.get('codes_size')
            if len(hex) == sensor_desc.get('payload_length')+l:
                values = sensor_desc.get('values')
                if values is not None:
                    if _extract_values(values, hex, data):
                        r = 1
                    else:
                        r = 0
                else:
                    r = 0
            else:
                r = 0
        else:
            r = 0
    else:
        r = 0
    return r


#extract all values stores in the payload
def _extract_values(values, hex, data):
    if values is not None:
        for value in values:
            _treat_value(value, hex, data)
        return 1
    else:
        return 0

#extract a value from string payload and store it in data
def _treat_value(desc, hex, data):
    c = desc.get("start")
    s = ''
    e = c + desc.get("length")
    while c < e:
        s = s + hex[c]
        c = c +1
    t = desc.get("type")
    n = desc.get("name")
    if t == "string":
        data[n] = s
    elif t == "int": 
        data[n] = _treat_int(s)
    elif t == "float":
        f = desc.get("factor")
        if f is None:
            f = 1
        data[n] = _treat_float(s, f)


#convert string to int
def _treat_int(val):
    return int(val, 16)


#convert string to float
def _treat_float(val, factor):
    i = _treat_int(val)
    return round(float(i)/factor,2)


#return configuration
def _parser_config():
    with open(config_file, 'r') as conf:
        config = json.load(conf)
    return config


#return extractor descripton
def _extractor_description():
    try:
        with open(extractor_file, 'r') as ext:
            extract = json.load(ext)
        return extract
    except Exception as e:
        return {}


if __name__ == "__main__":
    #load parser file
    _config = _parser_config()
    #configure and launch logger
    handler = RotatingFileHandler(_config['log']['file'],
                                   maxBytes=_config['log']['maxBytes'],
                                   backupCount=1)
    handler.setFormatter(Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(_config['log']['lvl'])

    # Start flask instances
    app.run(host=_config['server']['url'],
            port=int(_config['server']['port']),
            threaded=int(_config['server']['threaded']))

