from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import ImageCreateForm, SearchForm
from .models import Image
from common.decorators import ajax_required
from actions.utils import create_action
from django.conf import settings
import redis
from django.contrib.postgres.search import SearchVector, SearchQuery, \
                                           SearchRank

# Подключение к редис
r = redis.StrictRedis(host=settings.REDIS_HOST,
                      port=settings.REDIS_PORT,
                      db=settings.REDIS_DB)


@login_required
def image_create(request):
    if request.method == 'POST':
     
        form = ImageCreateForm(data=request.POST)
        if form.is_valid():

            cd = form.cleaned_data
            new_item = form.save(commit=False)

       
            new_item.user = request.user
            new_item.save()
            
            create_action(request.user, 'boomarked image', new_item)
            messages.success(request, 'Image added successfully')

          
            return redirect(new_item.get_absolute_url())
    else:
      
        form = ImageCreateForm(data=request.GET)

    return render(request,
                  'images/image/create.html',
                  {'section': 'images',
                   'form': form})


def image_detail(request, id, slug):
    image = get_object_or_404(Image, id=id, slug=slug)
    # Увеличиваем количество просмотров картинки на 1.
    total_views = r.incr('image:{}:views'.format(image.id))
    r.zincrby('image_ranking', image.id, 1)
  
    
    return render(request,
                  'images/image/detail.html',
                  {'section': 'images',
                   'image': image,
                   'total_views': total_views})


@ajax_required
@login_required
@require_POST
def image_like(request):
    image_id = request.POST.get('id')
    action = request.POST.get('action')
    if image_id and action:
        try:
            image = Image.objects.get(id=image_id)
            if action == 'like':
                image.users_like.add(request.user)
                create_action(request.user, 'likes', image)
            else:
                image.users_like.remove(request.user)
            return JsonResponse({'status':'ok'})
        except:
            pass
    return JsonResponse({'status':'ok'})


@login_required
def image_list(request):
    images = Image.objects.all()
    paginator = Paginator(images, 15)
    page = request.GET.get('page')
    try:
        images = paginator.page(page)
    except PageNotAnInteger:
       
        images = paginator.page(1)
    except EmptyPage:
        if request.is_ajax():
            return HttpResponse('')
        images = paginator.page(paginator.num_pages)
    if request.is_ajax():
        return render(request,
                      'images/image/list_ajax.html',
                      {'section': 'images', 'images': images})
    return render(request,
                  'images/image/list.html',
                   {'section': 'images', 'images': images})


@login_required
def image_ranking(request):
    image_ranking = r.zrange('image_ranking', 0, -1, desc=True)[:10]
    image_ranking_ids = [int(id) for id in image_ranking]

    most_viewed = list(Image.objects.filter(id__in=image_ranking_ids))
    most_viewed.sort(key=lambda x: image_ranking_ids.index(x.id))
    return render(request,
                  'images/image/ranking.html',
                  {'section': 'images',
                  'most_viewed': most_viewed})

def search_images(request):
    images = Image.objects.all()
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = SearchVector('title', weight='A')
            search_query = SearchQuery(query)
            results = Image.objects.annotate(rank=SearchRank(
                                             search_vector,
                                             search_query))\
                                             .filter(rank__gte=0.3)\
                                             .order_by('-rank')
    return render(request,
                  'images/image/search.html',
                  {'images': images,
                   'form': form,
                   'query': query,
                   'results': results})
