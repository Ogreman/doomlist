#!/bin/bash
gunicorn -b 0.0.0.0:$PORT application:application --log-file=-