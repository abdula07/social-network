from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from common.decorators import ajax_required
from actions.utils import create_action
from actions.models import Action
from .forms import LoginForm, UserRegistrationForm, \
                   UserEditForm, ProfileEditForm, \
                   SearchForm
from .models import Profile, Contact
from images.models import Image
from django.contrib.postgres.search import SearchVector, SearchQuery, \
										   SearchRank
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, \
                                  PageNotAnInteger           
    
def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user = authenticate(request,
                                username=cd['username'],
                                password=cd['password'])
            if user is not None:
                if user.is_active:
                    login(request, user)
                    return HttpResponse('Authenticated '\
                                        'successfully')
                else:
                    return HttpResponse('Disabled account')
            else:
                return HttpResponse('Invalid login')
    else:
        form = LoginForm()
    return render(request, 'account/login.html', {'form': form})


@login_required
def dashboard(request):

    actions = Action.objects.exclude(user=request.user)
    following_ids = request.user.following.values_list('id',
                                                       flat=True)
    if following_ids:
     
        actions = actions.filter(user_id__in=following_ids)
    actions = actions.select_related('user', 'user__profile')\
                     .prefetch_related('target')[:10]

    return render(request,
                  'account/dashboard.html',
                  {'section': 'dashboard',
                   'actions': actions})


def register(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        if user_form.is_valid():
          
            new_user = user_form.save(commit=False)
        
            new_user.set_password(
                user_form.cleaned_data['password'])
 
            new_user.save()

            Profile.objects.create(user=new_user)
            create_action(new_user, 'has create an account')
            return render(request,
                          'account/register_done.html',
                          {'new_user': new_user})
    else:
        user_form = UserRegistrationForm()
    return render(request,
                  'account/register.html',
                  {'user_form': user_form})


@login_required
def edit(request):
    if request.method == 'POST':
        user_form = UserEditForm(instance=request.user,
                                 data=request.POST)
        profile_form = ProfileEditForm(instance=request.user.profile,
                                       data=request.POST,
                                       files=request.FILES)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully')
        else:
            messages.error(request, 'Error updating your profile')
    else:
        user_form = UserEditForm(instance=request.user)
        profile_form = ProfileEditForm(instance=request.user.profile)
    return render(request,
                  'account/edit.html',
                  {'user_form': user_form,
                   'profile_form': profile_form})


@login_required
def user_list(request):
    users = User.objects.filter(is_active=True)
    paginator = Paginator(users, 15)
    page = request.GET.get('page')
    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)

    except EmptyPage:
        if request.is_ajax():
            return HttpResponse('')
        users = paginator.page(paginator.num_pages)

    if request.is_ajax():
        return render(request,
                      'account/user/ajax.html',
                      {'users': users})

    return render(request, 'account/user/list.html',
                  {'section': 'people',
                  'users': users})

@login_required
def user_detail(request, username):
    user = get_object_or_404(User, username=username, is_active=True)
    images = Image.objects.filter(user=user)
    return render(request, 'account/user/detail.html',
                  {'section': 'people',
                  'user': user,
                  'images': images})


@ajax_required
@require_POST
@login_required
def user_follow(request):
    user_id = request.POST.get('id')
    action = request.POST.get('action')
    if user_id and action:
        try:
            user = User.objects.get(id=user_id)
            if action == 'follow':
                Contact.objects.get_or_create(user_from=request.user,
                                              user_to=user)
                create_action(request.user, 'is following', user)
            else:
                Contact.objects.filter(user_from=request.user,
                                       user_to=user).delete()
            return JsonResponse({'status':'ok'})
        except User.DoesNotExist:
            return JsonResponse({'status':'ok'})
    return JsonResponse({'status':'ok'})

def search_user(request):
    user = User.objects.all()
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = SearchVector('username', weight='A')
            search_query = SearchQuery(query)
            results = User.objects.annotate(\
                            rank=SearchRank(search_vector,
                                            search_query))\
                            .filter(rank__gte=0.3).order_by('rank')
    return render(request,
                'account/user/search.html',
                {'user': user,
                'form': form,
                'query': query,
                'results': results})        