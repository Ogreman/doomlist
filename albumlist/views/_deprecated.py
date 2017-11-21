

# @app.route('/api/votes', methods=['GET'])
# @app.cache.cached(timeout=60 * 5)
# def api_all_votes():
#     try:
#         results = [
#             dict(zip(('id', 'artist', 'album', 'votes'), details))
#             for details in models.get_votes()
#         ]
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': results,
#         }))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/votes/<album_id>', methods=['GET'])
# def api_votes(album_id):
#     try:
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': models.get_votes_count(album_id),
#         }))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/vote', methods=['POST'])
# def api_vote():
#     form_data = flask.request.form
#     try:
#         album_id = form_data['album_id']
#         votes.add_to_votes(album_id)
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': models.get_votes_count(album_id),
#         }))
#     except (DatabaseError, KeyError):
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/votes/top', methods=['GET'])
# @app.cache.cached(timeout=60 * 5)
# def api_top():
#     try:
#         results = [
#             dict(zip(('id', 'artist', 'album', 'votes'), details))
#             for details in models.get_top_votes()
#         ]
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': results,
#         }))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))   
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/logs', methods=['GET'])
# def api_list_logs():
#     try:
#         response = flask.Response(json.dumps(models.get_logs()))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     return response



# @app.route('/api/tags/count', methods=['GET'])
# def api_tags():
#     try:
#         response = flask.Response(json.dumps({'text': 'success',
#             'tags': [tag for tag in models.get_tags()]}))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response
