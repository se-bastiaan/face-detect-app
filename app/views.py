import face_recognition
import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView, DeleteView, FormView, \
    TemplateView

from app.forms import UserEncodingCreateForm
from app.models import Album, UserEncoding
from face_detection.models import FaceEncoding
from face_detection.services import detector


@method_decorator(login_required, 'dispatch')
class AlbumsIndexView(ListView):
    template_name = 'app/index.html'
    model = Album
    context_object_name = 'albums'
    ordering = '-pk'


@method_decorator(login_required, 'dispatch')
class AlbumsDetailView(DetailView):
    template_name = 'app/album.html'
    model = Album
    context_object_name = 'album'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data = requests.get(
            f'https://thalia.nu/api/v1/photos/albums/{context["album"].pk}',
            headers={
                'Authorization': f'Token {self.request.session["token"]}'
            }).json()

        context['title'] = data['title']
        context['photos'] = data['photos']

        return context


@method_decorator(login_required, 'dispatch')
class MyPhotosView(TemplateView):
    template_name = 'app/album.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_encodings = UserEncoding.objects.filter(user=self.request.user)
        distance_function = 'min(1,'
        for user_encoding in user_encodings:
            encoding = user_encoding.encoding.fields_to_encoding()
            distance_function += 'sqrt('
            for i in range(0, 128):
                distance_function += f'power(field{i} - {encoding[i]}, 2) + '
            distance_function = distance_function[0:-2] + '),'
        distance_function = distance_function[0:-1] + ')'

        data_obj = FaceEncoding.objects.exclude(album_id=None).extra(
            select={
                'distance': distance_function
            },
            where=['distance < 0.49']
        ).order_by('distance')

        photos = []
        albums = {}

        for encoding in data_obj:
            if encoding.album_id in albums:
                data = albums[encoding.album_id]
            else:
                data = requests.get(
                    f'https://thalia.nu/api/v1/photos/albums/'
                    f'{encoding.album_id}/',
                    headers={
                        'Authorization':
                            f'Token {self.request.session["token"]}'
                    }).json()
                albums[encoding.album_id] = data
            for x in filter(lambda x: x['pk'] == encoding.image_id,
                            data['photos']):
                photos.append(x)

        context['title'] = 'Photos of me'
        context['photos'] = photos
        return context


@method_decorator(login_required, 'dispatch')
class UserEncodingIndexView(ListView):
    template_name = 'app/encodings/index.html'
    model = UserEncoding
    context_object_name = 'encodings'

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


@method_decorator(login_required, 'dispatch')
class UserEncodingCreateView(FormView):
    template_name = 'app/encodings/create.html'
    form_class = UserEncodingCreateForm
    success_url = reverse_lazy('encodings:index')

    def form_valid(self, form):
        encodings = detector.obtain_encodings(
            None, None, form.cleaned_data['upload_image'].file)

        for encoding in encodings:
            UserEncoding.objects.create(
                encoding=encoding,
                user=self.request.user
            )
        return HttpResponseRedirect(self.get_success_url())


@method_decorator(login_required, 'dispatch')
class UserEncodingDeleteView(DeleteView):
    template_name = 'app/encodings/delete.html'
    model = UserEncoding
    success_url = reverse_lazy('encodings:index')
