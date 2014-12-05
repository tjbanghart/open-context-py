import json
from django.http import HttpResponse
from opencontext_py.libs.solrconnection import SolrConnection
from opencontext_py.libs import viewutilities


def index(request):
    return HttpResponse("Hello, world. You're at the sets index.")


def html_view(request, spatial_context=None):
    return HttpResponse("Hello, world. You are trying to browse sets.")


def json_view(request, spatial_context=None):

    # Connect to Solr
    solr = SolrConnection().connection

    # Start building up our solr query
    query = {}

    # If the user does not provide a search term, search for everything
    query['q'] = request.GET.get('q', default='*:*')

    # Handle descriptive properties

    # Query string may contain multiple 'prop' parameters, so get all of them
    proplist = request.GET.getlist('prop')
    # Then each &prop gets its own list
    props = [prop.split(' ') for prop in proplist]

    prop_dict_list = []
    for prop in props:
        # If multi-select
        if any('||' in property for property in prop):
            prop_dict_list.append(
                viewutilities._process_multi_select_prop(prop))
        else:
            # Otherwise, if single-select
            prop_dict_list.append(
                viewutilities._process_single_select_prop(prop)
                )

    # return HttpResponse(prop_dict_list)

    # Handle Spatial Context
    context = viewutilities._process_spatial_context(spatial_context)
    # build solr query
    # TODO field list (fl)
    #query['fl'] = ['uuid', context_facet_request_field]
    query['facet'] = 'true'
    query['facet.mincount'] = 1
    query['fq'] = []
    query['fq'].append(context['fq'])
    query['facet.field'] = []
    query['facet.field'].append(context['facet.field'])

    if prop_dict_list:
        for prop in prop_dict_list:
            if prop['fq'] not in query['fq']:
                query['fq'].append(prop['fq'])
            if prop['facet.field'] not in query['facet.field']:
                query['facet.field'].append(prop['facet.field'])
    query['rows'] = 10
    query['start'] = 0
    query['debugQuery'] = 'true'
    response = solr.search(**query)
    # return HttpResponse(query_params.items())
    # return HttpResponse(context_list)
    # return HttpResponse(query['fq'])
    #return HttpResponse(json.dumps(response.facets['facet_fields'],
    #                    ensure_ascii=False, indent=4),
    #                    content_type="application/json; charset=utf8")
    return HttpResponse(json.dumps(response.raw_content,
                        ensure_ascii=False, indent=4),
                        content_type="application/json")
