with open("config/settings.py", "r") as f:
    content = f.read()

content = content.replace(
    """    @property
    def parsed_cors_origins(self) -> list[str]:
        return [p.strip() for p in self.cors_origins.split(",") if p.strip()]

    @property
    def parsed_trusted_hosts(self) -> list[str]:
        return [p.strip() for p in self.trusted_hosts.split(",") if p.strip()]""",
    """    @property
    def parsed_cors_origins(self) -> list[str]:
        if isinstance(self.cors_origins, list):
            return [str(p).strip() for p in self.cors_origins if str(p).strip()]
        return [p.strip() for p in str(self.cors_origins).split(",") if p.strip()]

    @property
    def parsed_trusted_hosts(self) -> list[str]:
        if isinstance(self.trusted_hosts, list):
            return [str(p).strip() for p in self.trusted_hosts if str(p).strip()]
        return [p.strip() for p in str(self.trusted_hosts).split(",") if p.strip()]""",
)

with open("config/settings.py", "w") as f:
    f.write(content)
