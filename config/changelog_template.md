## [{{ version }}] - {{ date }}
{% for change in changes %}
### {{ change.change_type }}
{% for commit in change.commits %}
- {{ commit.message }}
{% endfor %}
{% endfor %}
