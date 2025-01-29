import requests

HOST = 'http://127.0.0.1:5000'

class APIClient:
    def __init__(self, host: str):
        self.host = host
        self.auth = {}

    def request(self, url: str, data: dict):
        if self.auth == {} and url != '/api/login':
            raise RuntimeError('Not logged in')

        url = self.host + url
        response = requests.post(
            url,
            {
                **self.auth,
                **data,
            },
        ).json()

        return response

    def login(self, user: str, password: str) -> None:
        response = self.request(
            '/api/login',
            {
                'user': user,
                'password': password,
            },
        )

        self.auth = {
            'user': 'lormellm',
            'token': response['token'],
        }

    def logout(self):
        return self.request(
            '/api/logout',
            {},
        )

    def home(self):
        return self.request(
            '/api/home',
            {},
        )

    def notebook(self):
        return self.request(
            '/api/notebook',
            {},
        )

    def remove_postit(self):
        return self.request(
            '/api/remove_postit',
            {},
        )

    def mailbox(self, mailbox):
        return self.request(
            '/api/mailbox',
            {'mailbox': mailbox},
        )

    def read_mail(self, mail_id):
        return self.request(
            '/api/read_mail',
            {'mail_id': mail_id},
        )

    def transfer_mail(self, mail_transfer_id, from_mailbox, to_mailbox):
        return self.request(
            '/api/transfer_mail',
            {
                'mail_transfer_id': mail_transfer_id,
                'from_mailbox': from_mailbox,
                'to_mailbox': to_mailbox,
            }
        )

def test():
    user = input('Enter your username: ')
    password = input('Enter your password: ')

    client = APIClient(HOST)
    client.login(
        user,
        password,
    )

    print(client.home())
    print(client.logout())
    print(client.request('/api/mailbox', {
        'mailbox': 'a',
    }))
    print(client.request('/api/read_mail', {
        'mail_id': '108492',
    }))
    print(client.request('/api/transfer_mail', {
        'mail_transfer_id': '2077458',
        'from_mailbox': 'b',
        'to_mailbox': 'a',
    }))

if __name__ == '__main__':
    test()