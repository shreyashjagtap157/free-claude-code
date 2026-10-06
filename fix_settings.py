with open("config/settings.py") as f:
    content = f.read()

content = content.replace(
    'self.cors_origins.split(",")',
    '(self.cors_origins if isinstance(self.cors_origins, list) else self.cors_origins.split(","))',
)
content = content.replace(
    'self.trusted_hosts.split(",")',
    '(self.trusted_hosts if isinstance(self.trusted_hosts, list) else self.trusted_hosts.split(","))',
)

with open("config/settings.py", "w") as f:
    f.write(content)
