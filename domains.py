# https://developer.godaddy.com/doc/endpoint/domains

from email import header
from time import sleep
from urllib import response
from dotenv import load_dotenv
import requests
import os, sys
import json
import urllib.parse

if len(sys.argv) < 2:
    print('Usage: ' + sys.argv[0] + ' <KEY_SCOPE>')
    exit(-1)
KEY_TYPE = sys.argv[1]

GODADDY_API_URL='https://api.ote-godaddy.com/'
# GODADDY_API_URL='https://api.godaddy.com/'

def call_api(action):
    """ Call to the API, adding the headers and returning a json object """
    if action.startswith('/'):
        action = action[1:] 
    url_action = GODADDY_API_URL + '/' + action

    API_KEY = os.getenv('API_KEY_'+KEY_TYPE)
    SECRET_KEY = os.getenv('SECRET_KEY_'+KEY_TYPE)

    headers = {
        "Accept": "application/json",
        "Authorization": f'sso-key {API_KEY}:{SECRET_KEY}'
    }

    response = requests.request(
        "GET",
        url_action,
        headers=headers
    )

    return json.loads(response.text)

def get_dns_records(domain_name, dns_types):
    """ Return a list the dns types for a domain name """
    dns_name = urllib.parse.quote('@')  # Main dns

    res = []
    for dns_type in dns_types:
        sleep(1)    # Trying to minimize the limitation in number of calls per minute
        dns_details = call_api(f'v1/domains/{domain_name}/records/{dns_type}/{dns_name}')
        try:
            if 'code' in dns_details:
                error_code = dns_details['code']
                if error_code == 'TOO_MANY_REQUESTS':
                    print(error_code, 'Waiting 30s')
                    sleep(30)
                elif error_code == 'UNKNOWN_DOMAIN':
                    # This domain has not that dns type
                    continue
                else:
                    print('WARNING', dns_details)
            else:
                if dns_details != []:
                    res.extend(dns_details)
        except:
            print('ERROR', dns_details)
            exit(-1)
    #
    return res

if __name__ == '__main__':
    load_dotenv() # Take environment variables from .env
    REQUESTED_DNS = ['MX', 'TXT']

    res = {}
    my_domains = call_api('v1/domains')
    if 'code' in my_domains:
        print('ERROR:', my_domains)
        exit(-1)

    for domain in my_domains:
        domain_name = domain['domain']
        print('Checking... ' + domain_name)
        domain_dns = get_dns_records(domain_name, REQUESTED_DNS)
        if domain_dns != []:
            res[domain_name] = domain_dns

    print(res)
    
