"""Reviewed mechanical aliases used by deterministic Watch matching."""


ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "amazon web services": ("aws",),
    "angular": ("angularjs", "angular.js"),
    "apache airflow": ("airflow",),
    "apache kafka": ("kafka",),
    "apache spark": ("spark",),
    "artificial intelligence": ("ai",),
    "asp.net": ("asp net", "aspnet"),
    "back end": ("backend", "back-end", "server side", "server-side"),
    "behavior driven development": ("bdd", "behaviour driven development"),
    "business intelligence": ("bi",),
    "c sharp": ("c#", "csharp"),
    "c plus plus": ("c++", "cpp"),
    "change data capture": ("cdc",),
    "ci/cd": ("cicd", "continuous integration and delivery", "continuous delivery"),
    "command line interface": ("cli",),
    "continuous integration": ("ci",),
    "customer relationship management": ("crm",),
    "data loss prevention": ("dlp",),
    "data warehouse": ("dwh", "data warehousing"),
    "denial of service": ("dos",),
    "dev ops": ("devops", "dev-ops"),
    "dev sec ops": ("devsecops", "dev-sec-ops"),
    "django rest framework": ("drf",),
    "distributed denial of service": ("ddos",),
    "domain driven design": ("ddd", "domain-driven design"),
    "dotnet": (".net", "dot net"),
    "elastic search": ("elasticsearch",),
    "enterprise resource planning": ("erp",),
    "extract load transform": ("elt",),
    "extract transform load": ("etl",),
    "fast api": ("fastapi",),
    "front end": ("frontend", "front-end", "client side", "client-side"),
    "full stack": ("fullstack", "full-stack"),
    "golang": ("go",),
    "google cloud platform": ("gcp", "google cloud"),
    "graph ql": ("graphql",),
    "information security": ("infosec",),
    "information technology": ("it",),
    "infrastructure as code": ("iac",),
    "internet of things": ("iot",),
    "java script": ("javascript", "js", "ecmascript", "es6"),
    "key performance indicator": ("kpi",),
    "kubernetes": ("k8s",),
    "large language model": ("llm",),
    "machine learning": ("ml",),
    "mean stack": ("mean",),
    "mern stack": ("mern",),
    "micro services": ("microservices", "micro-services"),
    "microsoft azure": ("azure",),
    "microsoft sql server": ("sql server", "mssql"),
    "mongo db": ("mongodb", "mongo"),
    "natural language processing": ("nlp",),
    "next js": ("next.js", "nextjs"),
    "node js": ("node.js", "nodejs"),
    "nuxt js": ("nuxt.js", "nuxtjs"),
    "object oriented programming": ("oop", "object-oriented programming"),
    "open search": ("opensearch",),
    "open source software": ("oss",),
    "operating system": ("os",),
    "postgresql": ("postgres", "pgsql"),
    "power bi": ("powerbi",),
    "python": ("python3", "python 3"),
    "quality assurance": ("qa",),
    "rabbit mq": ("rabbitmq",),
    "react": ("reactjs", "react.js"),
    "react native": ("react-native",),
    "red hat enterprise linux": ("rhel",),
    "relational database management system": ("rdbms",),
    "representational state transfer": ("rest", "restful"),
    "retrieval augmented generation": ("rag", "retrieval-augmented generation"),
    "ruby on rails": ("rails", "ror"),
    "salesforce dot com": ("salesforce", "sfdc"),
    "search engine optimization": ("seo",),
    "security information and event management": ("siem",),
    "security operations center": ("soc",),
    "service level agreement": ("sla",),
    "simple storage service": ("s3",),
    "single page application": ("spa",),
    "single sign on": ("sso",),
    "site reliability engineering": ("sre", "site reliability engineer"),
    "software as a service": ("saas",),
    "software development engineer in test": ("sdet",),
    "software development kit": ("sdk",),
    "software development life cycle": ("sdlc",),
    "spring boot": ("springboot",),
    "structured query language": ("sql",),
    "terraform": ("hashicorp terraform",),
    "test driven development": ("tdd", "test-driven development"),
    "transport layer security": ("tls",),
    "type script": ("typescript", "ts"),
    "user experience": ("ux",),
    "user interface": ("ui",),
    "virtual private cloud": ("vpc",),
    "virtual private network": ("vpn",),
    "visual studio code": ("vscode", "vs code"),
    "vue": ("vuejs", "vue.js"),
    "web application firewall": ("waf",),
    "web services": ("webservices",),
    "work from home": ("wfh",),
}


_ALIAS_TO_CANONICAL = {
    alias.casefold(): canonical for canonical, aliases in ALIAS_MAP.items() for alias in aliases
}


def variants_for(term: str) -> tuple[str, ...]:
    """Return one reviewed equivalence group, preserving the submitted term first."""
    normalized = " ".join(term.casefold().split())
    canonical = normalized if normalized in ALIAS_MAP else _ALIAS_TO_CANONICAL.get(normalized)
    if canonical is None:
        return (term,)
    candidates = (term, canonical, *ALIAS_MAP[canonical])
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = " ".join(candidate.casefold().split())
        if key and key not in seen:
            result.append(candidate)
            seen.add(key)
    return tuple(result)


def expand_with_aliases(terms: list[str]) -> list[str]:
    """Flatten reviewed equivalence groups while retaining stable order."""
    expanded: list[str] = []
    seen: set[str] = set()
    for term in terms:
        for variant in variants_for(term):
            key = variant.casefold()
            if key not in seen:
                expanded.append(variant)
                seen.add(key)
    return expanded
