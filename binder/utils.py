
def namespace_params(ns, params):
    ns_params = {}
    for p in params:
        ns_params[ns + '.' + p] = params[p]
    return ns_params

def make_patterns(params):
    return [(re.compile("{{" + k + "}}"), '{0}'.format(params[k])) for k in params]

def fill_template_string(template, params):
    res = make_patterns(params)
    replaced = template
    for pattern, new in res:
        replaced = pattern.sub(new, replaced)
    print_res = map(lambda (p, s): (p.pattern, s), res)
    return replaced

def fill_template(template_path, params):
    try:
        res = make_patterns(params)
        with open(template_path, 'r+') as template:
            raw = template.read()
        with open(template_path, 'w') as template:
            replaced = raw
            for pattern, new in res:
                replaced = pattern.sub(new, replaced)
            template.write(replaced)
    except (IOError, TypeError) as e:
        print("Could not fill template {0}: {1}".format(template_path, e))