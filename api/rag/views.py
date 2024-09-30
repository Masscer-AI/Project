from django.http import JsonResponse
from .managers import chroma_client

def test_chunks(request):
    collection_name = "charly-collection"
    query_text = request.GET.get('q', 'Where did you study?')
    
    results = chroma_client.get_results(
        collection_name=collection_name, query_text=query_text,
        n_results=1
    )

    data = {"results": results}
    return JsonResponse(data)
