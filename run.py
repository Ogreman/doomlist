#!flask/bin/python
import os

from application import application as app

app.cache.clear()
app.run(debug=app.config.get('DEBUG', True), port=int(os.getenv('DEV_PORT', 5000)))
