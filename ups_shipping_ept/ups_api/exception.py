class ConnectionError(Exception):
    def __init__(self, msg, response):
        super(ConnectionError, self).__init__('%s' % msg)
        self.message = '%s' % msg
        self.response = response

    def __str__(self):
        return repr(self.message)