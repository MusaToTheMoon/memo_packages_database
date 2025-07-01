import requests

def fetch_code_from_github(url):
    """
    Fetches raw Java source from GitHub. Converts regular GitHub URLs to raw URLs if needed.
    """
    if "github.com" in url and "raw.githubusercontent.com" not in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        print(url)

    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch source: {response.status_code}")

    return response.text

fetch_code_from_github("https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/lang/String.java")