import requests
import bs4
import secrets
from json import load, dumps

DEBUG = True
GEPI_HOST = 'https://lfabuc.fr/ac'

def gepi_url(url: str) -> str:
    return GEPI_HOST + url

URLS = {
    'LOGIN': gepi_url('/login.php'),
    'LOGOUT': gepi_url('/logout.php'),
    'HOME': gepi_url('/accueil.php'),
    'NOTEBOOK': gepi_url('/cahier_texte/consultation.php'),
    'MAILBOX': gepi_url('/mod_alerte/form_alerte_bis.php'),
    'READ_MAIL': gepi_url('/mod_alerte/lect_alerte.php'),
}

def api_request(func):
    def decorated(self, json: dict) -> dict | None:
        if DEBUG:
            print(f'API request {json}')

        response = {'status': 'invalid'}

        try:
            session = self.get_session(json)

            if session is None:
                if DEBUG:
                    print('Failed to connect to session')
                return

            client = GepiClient(session)

            if DEBUG:
                print('Connected to client')
                print('Running function')

            response = func(self, json, client)
        finally:
            return response

    return decorated

class GepiSessionNew:
    user: str | None = None
    password: str | None = None
    token: str | None = None

    def __init__(self) -> None:
        self.session = requests.Session()

    def save(self) -> dict:
        return {
            'user': self.user,
            'password': self.password,
            'token': self.token,
            'cookie': self.session.cookies.get('GEPI'),
        }

    @staticmethod
    def load(session: dict):
        gepi_session = GepiSessionNew()
        gepi_session.session.cookies.set(
            'GEPI',
            session['cookie'],
        )
        gepi_session.user = session['user']
        gepi_session.password = session['password']
        gepi_session.token = session['token']

        return gepi_session

    def login(self, user: str, password: str, generate_token: bool):
        status, response = self.post(
            URLS['LOGIN'],
            data = {
                'login': user,
                'no_anti_inject_password': password,
                'submit': 'Valider',
            },
        )

        if status == 'ok' and generate_token:
            if DEBUG:
                print('Login successful')

            self.user = user
            self.password = password
            self.token = secrets.token_hex(256) # very big

        return {'status': status}

    def logout(self):
        status, response = self.get(URLS['LOGOUT'], retry = False)

        if status == 'logout':
            self.session.cookies.clear()

        return {'status': status}

    @staticmethod
    def check(response) -> str:
        if 'logout.css' in response.text:
            if DEBUG:
                print('Logged out')

            return 'logout'
        elif 'Échec de la connexion à Gepi' in response.text:
            if DEBUG:
                print('Invalid login')

            return 'failed'
        elif response.status_code == 404:
            return 'invalid'
        elif "TENTATIVE D'INTRUSION" in response.text:
            print('Breach')

            return 'breach'
        else:
            return 'ok'

    def get(self, url: str, params: dict | None = None, retry: bool = True) -> tuple:
        if params is None:
            params = {}

        if DEBUG:
            print(f'GET {url} {params}')

        response = self.session.get(
            url,
            params = params,
        )
        status = self.check(response)

        if status == 'logout' and retry:
            if DEBUG:
                print(f'Retrying with {self.user} {self.password}')

            self.login(self.user, self.password, False)

            return self.get(url, params, False)

        return status, response

    def post(self, url: str, data: dict | None = None, retry: bool = True) -> tuple:
        if data is None:
            data = {}

        if DEBUG:
            print(f'GET {url} {data}')

        response = self.session.post(
            url,
            data = data,
        )
        status = self.check(response)

        if status == 'retry' and retry:
            if DEBUG:
                print(f'Retrying with {self.user} {self.password}')

            self.login(self.user, self.password, False)

            return self.post(url, data, False)

        return status, response


class GepiClient:
    def __init__(self, new_session: GepiSessionNew) -> None:
        self.session = new_session

    def use(self, new_session: GepiSessionNew) -> None:
        self.session = new_session

    def logout(self) -> dict:
        return {'status': self.session.logout()['status']}

    def home(self) -> dict:
        # TODO: last connexion
        # TODO: new mails
        # TODO: user info (name, class)
        status, response = self.session.get(URLS['HOME'])

        if status != 'ok':
            return {'status': status}

        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        postit_div = soup.find('div', class_ = 'postit')
        postit_dict = {
            'content': ''
        }

        if postit_div is not None:
            postit = postit_div.text.strip()
            form = postit_div.find('form')
            csrf_alea = form.find('input', {'name': 'csrf_alea'})['value']
            supprimer_message = form.find('input', {'name': 'supprimer_message'})['value']
            postit_dict = {
                'content': postit,
                'csrf_alea': csrf_alea,
                'supprimer_message': supprimer_message
            }

        return {
            'status': 'ok',
            'postit': {
                'content': postit_dict,
            }
        }

    def remove_postit(self) -> dict:
        home = self.home()
        status = home['status']
        postit = home['postit']

        if status != 'ok':
            return {'status': status}

        if postit['content'] == '':
            return {'status': 'invalid'}

        status, response = self.session.post(
            URLS['HOME'],
            data = {
                'csrf_alea': postit['csrf_alea'],
                'supprimer_message': postit['supprimer_message'],
            }
        )

        return {'status': status}

    def notebook(self) -> dict:
        status, response = self.session.get(URLS['NOTEBOOK'])

        if status != 'ok':
            return {'status': status}

        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        notebook_div = soup.find('div', class_ = 'cel_trav_futur')
        notebook = {}
        day = ''
        date_mask = len('Travaux personnels pour le ')
        homework_id_mask = len('div_travail_')
        for child in notebook_div.find_all(['h3', 'div']):
            if child.name == 'h3':
                day = child.text.strip()[date_mask:]
                notebook[day] = []
            else:
                if child.get('class') is None:
                    continue

                homework: dict = {
                    'test': child.find('img', {'title': 'contrôle'}) is not None,
                    'content': '',
                    'id': child.get('id')[homework_id_mask:],
                }

                if homework['test']:
                    subject, duration = child.find('h4').text.strip().split("durée d'effort estimée (en min) ")
                else:
                    subject, duration = child.find('h4').text.strip().split("durée estimée pour ce travail (en min) ")

                duration = duration[:-2]
                subject_split = subject.split(' ')
                short_subject = subject_split[0].capitalize()
                classes = ''
                teacher = ''

                for i in subject_split:
                    if i == '':
                        continue

                    if i[0] == '[':
                        classes = i[1:-1]
                    elif i[0] == '(':
                        teacher = i[1:]
                    elif teacher != '' and not ' ' in teacher:
                        teacher += f' {i}'

                homework['subject'] = short_subject
                homework['duration'] = duration
                homework['classes'] = classes
                homework['teacher'] = teacher

                for p in child.find_all('p'):
                    if homework['content'] != '':
                        homework['content'] += '\n'

                    homework['content'] += p.text.strip()

                notebook[day].append(homework)

        return {
            'status': 'ok',
            'notebook': notebook,
        }

    def mailbox(self, mailbox: str) -> dict:
        if not mailbox in ['a', 'b', 'z']:
            return {'status': 'invalid'}

        status, response = self.session.get(
            URLS['MAILBOX'],
            params = {
                'mode': 'afficher_boite_' + mailbox
            }
        )

        if status != 'ok':
            return {'status': status}

        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        mails = []
        read_mail_mask = len('lect_alerte.php?rg=')
        for mail_tr in soup.find_all('tr'):
            mail_tds = mail_tr.find_all('td')
            if len(mail_tds) == 0:
                continue

            a_href = mail_tds[0].find('a')['href'][read_mail_mask:]
            a_href = a_href.split('&')[0]
            a_href_transfer = mail_tds[4].find('a')['href'].split('id_alerte=')[1]
            date = mail_tds[1].text.split(' à ')
            mail = {
                'id': int(a_href),
                'transfer_id': int(a_href_transfer),
                'day': date[0],
                'time': date[1],
                'author': mail_tds[2].text.strip(),
                'subject': mail_tds[3].text.strip(),
            }
            mails += [mail]

        return {
            'status': 'ok',
            'mails': mails,
        }

    def read_mail(self, mail_id: int) -> dict:
        status, response = self.session.get(
            URLS['READ_MAIL'],
            params = {
                'rg': mail_id,
            },
        )

        if status != 'ok':
            return {'status': status}

        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        mail_td = soup.find('td')
        content = mail_td.text
        content = content.split('Post scriptum')[0].strip()
        content = content.split('Désabonnement')[0].strip()
        content = content.split('laus:')[0].strip()

        return {
            'status': 'ok',
            'content': content,
        }


    def transfer_mail(self, mail_transfer_id: int, from_mailbox: str, to_mailbox: str) -> dict:
        if not {from_mailbox, to_mailbox} in [{'a', 'b'}, {'b', 'z'}]: # from a to z does not work
            return {'status': 'invalid'}

        status, response = self.session.get(
            URLS['MAILBOX'],
            params = {
                'action': f'de_{from_mailbox}_vers_{to_mailbox}',
                'id_alerte': mail_transfer_id,
            },
        )

        return {
            'status': status,
        }

    # TODO: homeworks done/undone (breaches)
    # TODO: account
    # TODO: notes
    # TODO: bulletins
    # TODO: collect boxes (hard)

class API:
    def __init__(self):
        self.sessions = {}

    def save(self):
        path_mask = len('gepi_api.py')
        json_path = __file__[:-path_mask] + '.sessions.json'
        sessions = []

        for session in self.sessions.values():
            sessions += [session.save()]

        json = dumps(sessions)

        if DEBUG:
            print(f'Saving sessions {json}')

        with open(json_path, 'w') as f:
            f.write(json)  # dump

    @staticmethod
    def load():
        path_mask = len('gepi_api.py')
        json_path = __file__[:-path_mask] + '.sessions.json'
        api = API()

        with open(json_path, 'r') as f:
            sessions = load(f)

        if DEBUG:
            print(f'Loaded sessions {sessions}')

        for session in sessions:
            api.sessions[session['user']] = GepiSessionNew.load(session)

        if DEBUG:
            print(f'Saved sessions {api.sessions}')

        return api

    def login(self, json: dict) -> dict | None:
        response = {
            'status': 'invalid',
        }

        try:
            user = json['user']
            password = json['password']

            if DEBUG:
                print(f'Logging in {user} {password}')

            session = GepiSessionNew()

            if DEBUG:
                print(f'Created session')

            status = session.login(
                user,
                password,
                True,
            )['status']

            if DEBUG:
                print(f'Login status {status}')

            if status == 'ok':
                self.sessions[user] = session

                response = {
                    'status': 'ok',
                    'token': session.token,
                }
            else:
                response = {'status': status}
        finally:
            return response

    def get_session(self, json: dict) -> GepiSessionNew | None:
        response = None

        try:
            user = json['user']
            token = json['token']

            session = self.sessions[user]

            if session.token == token:
                response = session
        finally:
            return response

    @api_request
    def logout(self, json: dict, client: GepiClient) -> dict:
        return client.logout()

    @api_request
    def home(self, json: dict, client: GepiClient) -> dict:
        return client.home()

    @api_request
    def notebook(self, json: dict, client: GepiClient) -> dict:
        return client.notebook()

    @api_request
    def remove_postit(self, json: dict, client: GepiClient) -> dict:
        return client.remove_postit()

    @api_request
    def mailbox(self, json: dict, client: GepiClient) -> dict:
        return client.mailbox(
            mailbox = json['mailbox']
        )

    @api_request
    def read_mail(self, json: dict, client: GepiClient) -> dict:
        return client.read_mail(
            mail_id = json['mail_id']
        )

    @api_request
    def transfer_mail(self, json: dict, client: GepiClient) -> dict:
        return client.transfer_mail(
            mail_transfer_id = json['mail_transfer_id'],
            from_mailbox = json['from_mailbox'],
            to_mailbox = json['to_mailbox'],
        )

    def route(self, path: str, json: dict) -> dict:
        if DEBUG:
            print(f'Routing {path} {json}')

        # if path[-1] == '/':
        #     path = path[:-1]

        match path:
            case '/api/login':
                return self.login(json)
            case '/api/logout':
                return self.logout(json)
            case '/api/home':
                return self.home(json)
            case '/api/notebook':
                return self.notebook(json)
            case '/api/remove_postit':
                return self.remove_postit(json)
            case '/api/mailbox':
                return self.mailbox(json)
            case '/api/read_mail':
                return self.read_mail(json)
            case '/api/transfer_mail':
                return self.transfer_mail(json)
            case _:
                return {'status': 'invalid'}