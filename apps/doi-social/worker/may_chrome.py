"""Local transport to MinMin's managed Chromium host, without GPM Login."""
from may_gpm import LoiGPM


class ChromeMinMin:
    ten = 'chromium'

    def __init__(self, server, nhat_ky=None):
        self.server = server
        self.job = None

    def for_job(self, job):
        self.job = job

    def ds_profile(self):
        try:
            return self.server._req('GET', '/doi-social/may/chrome/profiles')['muc']
        except Exception as exc:
            raise LoiGPM('Chrome MinMin chưa sẵn sàng') from exc

    def mo(self, pid):
        return self.server._req('POST', '/doi-social/may/chrome/open',
                                {'profile': pid, 'job': self.job['id']})['endpoint']

    def dong(self, pid):
        self.server._req('POST', '/doi-social/may/chrome/close',
                         {'profile': pid, 'job': self.job['id']})
