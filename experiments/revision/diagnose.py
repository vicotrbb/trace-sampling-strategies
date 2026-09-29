"""Fixed trace-only fault localization. No access to experiment truth or policy."""

def attributes(span):
    return {a['key']: next(iter(a['value'].values())) for a in span.get('attributes', [])}

def diagnose(spans):
    """Return (mechanism, service) or explicit abstention from observed evidence."""
    for span in spans:
        attrs = attributes(span)
        if span.get('name') == 'db.query' and attrs.get('db.response.status_code') == '42P01':
            return ('sql_schema', 'postgresql')
    for span in spans:
        if span.get('name') == 'db.query' and int(span['endTimeUnixNano']) - int(span['startTimeUnixNano']) >= 250_000_000:
            return ('database_latency', 'postgresql')
    for span in spans:
        attrs = attributes(span)
        if span.get('name') == 'domain.validate' and 'domain.expected' in attrs and 'domain.actual' in attrs:
            if int(attrs['domain.expected']) != int(attrs['domain.actual']):
                return ('domain_invariant', attrs.get('domain.owner', 'unknown'))
    return ('abstain', 'unknown')
