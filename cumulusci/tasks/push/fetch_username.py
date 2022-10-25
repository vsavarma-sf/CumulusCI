import requests

from cumulusci.core.tasks import BaseTask
from cumulusci.utils.http.requests_utils import safe_json_from_response


class FetchUsernameTask(BaseTask):
    """Base class for tasks that talk to any public REST API."""

    task_options = {
        "api_host": {
            "description": "Hostname of the API Server",
            "required": True,
        },
        "path": {
            "description": "Path of the endpoint",
            "required": True,
        },
        "method": {
            "description": "Path of the endpoint, defaults to GET"
        },
        "headers": {
            "description": "Headers to pass in the request"
        },
        "payload": {
            "description": "Payload to pass for any of POST PUT DELETE PATCH request"
        }
    }

    # Remove any leading and trailing / and spaces or many more we want to achive in future
    def _sanitize_input(self, content):
        content = content.strip("/")
        return content.strip(" ")
    
    def _init_options(self, kwargs):
        super(FetchUsernameTask, self)._init_options(kwargs)
        self.base_url = self._sanitize_input(self.options.get("api_host"))
        self.path = self._sanitize_input(self.options.get("path"))
        self.method = self.options.get("method", "GET")
        self.headers = self.options.get("headers", [])
        self.api = requests.Session()

    def _call_api(self, **kwargs):
        next_url = f"{self.base_url}/{self.path}"

        request_headers = {}
        if self.headers:
            for header in self.headers:
                self.logger.info("Header: {}".format(header))
                header_type, header_desc = header.split(":")
                request_headers[header_type] = header_desc

        response = self.api.request(self.method, next_url, headers=request_headers, **kwargs)
        if not response.ok:
            raise requests.exceptions.HTTPError(response.content)

        try:
            return response.json()
        except:
            return {}

    def _run_task(self):
        response = self._call_api()
        self.logger.info(f"Status: {response.get('meta').get('status')}")
        username = response.get('data').get('requests')[0].get('scripts')[0].get('output').strip()
        self.logger.info(f"User: '{username}'")
