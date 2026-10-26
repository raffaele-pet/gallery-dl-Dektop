"""Use the OS certificate store and bounded retries for normal HTTP requests."""
import truststore

# Application-wide setup, before requests/gallery-dl create their SSL contexts.
# Windows can retrieve missing intermediate certificates without disabling HTTPS.
truststore.inject_into_ssl()


def http_session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    session = requests.Session()
    retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.5,
                  status_forcelist=(500, 502, 503, 504),
                  allowed_methods=('GET', 'HEAD'), respect_retry_after_header=False)
    session.mount('https://', HTTPAdapter(max_retries=retry))
    session.mount('http://', HTTPAdapter(max_retries=retry))
    return session
