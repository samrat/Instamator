from flask import Flask, render_template, make_response, redirect, request, url_for, session
import requests
from instagram.client import InstagramAPI
import simplejson as json
import PyRSS2Gen
import hashlib
import redis

app = Flask(__name__)
app.secret_key = 'secretkey' 

redis_server = redis.Redis("localhost") #redis configuration for localhost

CONFIG = {
'redirect_uri' : "http://instamator.ep.io/authenticate",
'client_id' : 'client_id',
'client_secret' : 'client_secret'
}

unauthenticated_api = InstagramAPI(**CONFIG)

@app.route('/')
def index():
    if 'api' in session:
        user_id = session['api'].user().id
        hash_id = hashlib.sha1(str(user_id)).hexdigest() 
        access_token = session['access_token']
        redis_server.set(hash_id, access_token)
        return render_template('index.html', hash_id=hash_id)

    elif 'api' not in session:
        try:
            url = unauthenticated_api.get_authorize_url(scope=["likes"])
            return render_template('index.html', login=url)
        except Exception, e:
            print e

@app.route('/authenticate')
def authenticate():
    code = request.args['code']
    
    try:
        access_token = unauthenticated_api.exchange_code_for_access_token(code)
        if not access_token:
            return 'Could not get access token'
        
        api = InstagramAPI(access_token=access_token)
        session['access_token'] = access_token
        session['api'] = api
        session['user_id'] = api.user().id
         
        return redirect(url_for('index'))
    except Exception, e:
        print e
    return redirect(url_for('index'))

@app.route('/<hash_id>/text')
def makeText(hash_id):
    '''Makes Text file about Instagram likes
    hash_id: unique id for user 
    '''
    if 'api' in session:
        api = session['api']
    else: 
        access_token = redis_server.get(hash_id)
        api = InstagramAPI(access_token=access_token)
    liked = api.user_liked_media(count = -1)
    user_id = api.user().id

    textcontent = []
    for i in liked[0]:
        textcontent.append(i.images['standard_resolution'].url)

    text_response = "\n".join(textcontent)
    response = make_response(text_response)
    response.headers['Content-Type'] = 'text/plain'
    return response

@app.route('/<hash_id>/json')
def makeJson(hash_id):
    if 'api' in session:
        api = session['api']
    else: 
        access_token = redis_server.get(hash_id)
        api = InstagramAPI(access_token=access_token)

    liked = api.user_liked_media(count=-1)
    user_id = api.user().id
    #print liked
    
    dumpcontent = []
    for i in liked[0]:
        tmpdict = {}
    
        if i.caption:
            tmpdict["description"] = "<img src='%s' title='%s'/>" % (i.images['standard_resolution'].url, i.caption.text)
            tmpdict["title"] = i.caption.text
        else:
            tmpdict["description"] = "<img src='%s' title=''/>" % (i.images['standard_resolution'].url)
            tmpdict["title"] = ''
        tmpdict["link"] = i.images['standard_resolution'].url
     
        dumpcontent.append(tmpdict)
    
    opendump = json.dumps(dumpcontent)
    response = make_response(str(opendump))
    response.headers['Content-Type'] = 'application/json'
    
    return response

@app.route('/<hash_id>/rss')
def makeRss(hash_id):
    if 'api' in session:
        api = session['api']
    else: 
        access_token = redis_server.get(hash_id)
        api = InstagramAPI(access_token=access_token)
    liked = api.user_liked_media(count=-1)
    username = api.user().username
    user_id = api.user().id
    

    items = [] 
    for i in liked[0]:
        if i.caption:
            title = i.caption.text
        else: title=''
        link = i.images['standard_resolution'].url
        description = "<img src='%s' title='%s'/>" % (link, title)
        item = PyRSS2Gen.RSSItem(title,link,description)
        items.append(item)
    
    title = "%s's Instamator RSS Feed" % username
    link = "http://instamator.ep.io/%s/rss" % hash_id 
    rss = PyRSS2Gen.RSS2(
    title= title,
    description ='',
    link=link,
    items=items,
    )

    rss_response = rss.to_xml()
    response = make_response(rss_response)
    response.headers['Content-Type'] = 'application/rss+xml'
    return response

if __name__ == '__main__':
    app.run(debug=False)
