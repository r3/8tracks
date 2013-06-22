import requests, json
import subprocess, threading
from pprint import pprint

from getpass import getpass as gp
''' 
We need to contact 8tracks with the API key.
First things first, let's set up our url and API variables.
'''
base_url = 'http://8tracks.com/'
API = 'd9a4ca3f43e70029e3619fdc7869d1cd608141e0.'

def format_play_url(url):
    '''
    Formats URL's into something that mpg123 can actually understand
    '''
    
    play_soup = BeautifulSoup(url)
    player = play_soup('url')
    playing = ''
    for i in player:
        playing = i.string
    return playing


def display_mixes():
    '''
    Request 8tracks' Top mixes.
    Displays id, name, and track count.
    returns trackDict to invoking function
    '''
    request = json.loads(requests.get(base_url + 'mixes.json?api_key=' + API).content)
    for ident, name, noTracks in zip([x[u'id'] for x in request[u'mixes']],[x[u'name'] for x in request[u'mixes']], [x[u'tracks_count'] for x in request[u'mixes']]):
        print('id: {}\nName: {}\nTrack Count: {}'.format(ident, name.encode('utf-8'), noTracks))
    
    trackDict = {}
    for ident, noTracks in zip([x[u'id'] for x in request[u'mixes']], [x[u'tracks_count'] for x in request[u'mixes']]):
        trackDict[ident] = noTracks
        
    return trackDict

def mix_selection():
    '''
    Calls to display_mixes to present list/info. 
    Allows user to select the mix.
    Returns id, noTracks to invoking function.
    '''
    trackDict = display_mixes()
    response = raw_input('Which mix do you want to listen to?: ')
    for key in trackDict.keys():
        if response in str(key):
            return key, trackDict[key]

def play_token():
    '''
    For playing, we need to first request a new play token. 
    URL FORM: base_url/sets/new.json?[API]
    '''
    new_request = json.loads(requests.get(base_url + '/sets/new.json?api_key=' + API).content)
    return new_request[u'play_token']

def report_performance(playToken, mix_id, track_id):
    '''
    8tracks needs to report each play to remain legal. A song is counted as "performed" at the 30 second mark.
    http://8tracks.com/sets/[play_token]/report.xml?track_id=[track_id]&mix_id=[mix_id]
    '''    
    print("Now reporting song as performed. Yay for being legal.")
    playToken, mix_id, track_id = playToken, mix_id, track_id
    status = requests.get(base_url + 'sets/%s/report.?track_id=%s&mix_id=%s&api_key=%s' % (play_token,track_id,mix_id,API))

def play_stream(playing, blocking):
    '''
    Current implementation is to open mpg123 as subprocess to play stream.
    '''
    stream = subprocess.Popen(['mpg123', playing])
    if blocking:
        stream.wait()
    return

def print_metadata(artist, track):
    '''
    This prints information about what is playing.
    '''
    print('*****\nNow Playing "{}" by {}\n*****'.format(track.encode('utf-8'), artist.encode('utf-8')))
    '''
    Eventually, this will also display 'Track {} of {}' using songNo (current track number) and trackNo (total number of tracks in a mix.)
    '''

def skip_track(playToken, mixID):
    '''
    Skip Track
    
    Checks to see if skips are allowed, if true, skip to next URL Stream. 
    If false, display so to user.
    '''
    skipResponse = requests.get(base_url + '/sets/{}/skip.json?mix_id={}&api_version=2&api_key={}'.format(playToken,mixID,API))
    skipJSON = json.loads(skipResponse.content)
    if skipJSON[u'status'] == '403 Forbidden':
        print('*****\n' + skipJSON[u'notices'] + ' You may skip again in {} seconds.'.format(skipJSON[u'skip_allowed_in_seconds']) + '\n*****')
    else:
        if skipJSON[u'set'][u'skip_allowed'] == 'True':
            play_stream(format_play_url(skipJSON[u'set'][u'track'][u'url']), blocking=True)

def next_track(playToken, mixID):
    '''
    This will get the next URL for playing. First, let's check and make sure we aren't
    at the end of the playlist. Then, get next URL and feed it into the stream.
    URL FORM: http://8tracks.com/sets/[play_token]/next.xml?mix_id=[mix_id]?api_key=[API]
    '''
    nextQuery = requests.get(base_url + 'sets/%s/next.json?mix_id=%s&api_key=%s' % (playToken, mixID, API))
    nextJSON = json.loads(nextQuery.content)
    '''
    Are we at the end of the mix?
    If so, play next mix.
    '''
    if nextJSON[u'set'][u'at_end'] != 'false':
        print_metadata(nextJSON[u'set'][u'track'][u'performer'], nextJSON[u'set'][u'track'][u'name'])
        play_stream(nextJSON[u'set'][u'track'][u'url'], blocking=True)
    else:
        next_mix = json.loads(requests.get(base_url + 'sets/%s/next_mix.json?mix_id=%s&api_key=%s' % (playToken, mix_id, API)).content)
        play_stream(next_mix[u'set'][u'track'][u'url'])
    
'''
Done. Now let's actually start the stream.
url form: http://8tracks.com/sets/play_token/play.xml?mix_id?api_key=
Note: Currently broken, but I can hack on this some more.
'''
def verify_user():
    '''
    Get username and password from user. Currently unused function. 
    Make an https/ssl POST request to https://8tracks.com/sessions.json with data as login=[login]&password=[pass]. 
    Will return with embedded user-token to be used throughout site.
    Afterwards, return the user-token to invoking function.
    '''
    username = raw_input('Username: ')
    password = gp()
    data = 'login={}&password={}'.format(username, password)
    secureHTTPS = 'https://8tracks.com/'
    verify = requests.post(secureHTTPS + 'sessions.json', data=data)
    verifyJSON = json.loads(verify.content)
    return verifyJSON[u'user_token']

def start_stream():
    '''
    Main function. First grabs a play-token from 8tracks to keep track of sessions
    Next, asks user for a mix, then starts play/next/play/next cycle.
    '''
    playToken = play_token()
    mixID, noTracks = mix_selection()
    queryURL = requests.get(base_url + 'sets/{}/play.json?mix_id={}&api_version=3&api_key={}'.format(playToken,mixID,API))
    play_request = json.loads(queryURL.content)
    
    playing = play_request[u'set'][u'track'][u'url']
    trackID = play_request[u'set'][u'track'][u'id']
    
    threading.Timer(30, report_performance, args=[playToken, mixID, trackID]).start()
    
    print_metadata(play_request[u'set'][u'track'][u'performer'], play_request[u'set'][u'track'][u'name'])
    
    play_stream(playing, blocking=True)
    
    songNo = 1
    while songNo < noTracks:
        if songNo == noTracks:
            break
        else:
            threading.Timer(30, report_performance, args=[playToken, mixID, trackID]).start()
            next_track(playToken, mixID)
            songNo += 1

if __name__ == '__main__':
    start_stream()
