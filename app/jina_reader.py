import requests

class JinaReader:
    def read(self, url):
        jina_url = "https://r.jina.ai/" + url
        try:
            response = requests.get(jina_url)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            return response.text
        except requests.RequestException as e:
            return f"Error fetching {jina_url}: {str(e)}"
