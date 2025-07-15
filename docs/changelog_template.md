{% import 'cz_conventional_commits/macros.md' as macros %}

{%- for version, version_commits in changelog.items() -%}
    {%- if not version_commits.date %}
        {% set version_commits_date = "Unreleased" %}
    {% else %}
        {% set version_commits_date = version_commits.date %}
    {% endif -%}

    {%- if version and version_commits.url -%}
        ## [{{ version }}]({{ version_commits.url }}) ({{ version_commits_date }})
    {%- elif version -%}
        ## {{ version }} ({{ version_commits_date }})
    {%- endif -%}

    {{ macros.render_commits(version_commits.commits, with_body=true) }}
{%- endfor -%}