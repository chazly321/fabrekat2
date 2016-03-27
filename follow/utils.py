from django.core.urlresolvers import reverse
from django.db.models.fields.related import ManyToManyField, ForeignKey
from follow.models import Follow
from follow.registry import registry, model_map
from designprofiles.utils import add_project_to_working_projects, remove_project_from_working_projects

def get_followers_for_object(instance):
    return Follow.objects.get_follows(instance)

def register(model, field_name=None, related_name=None, lookup_method_name='get_follows'):
    """
    This registers any model class to be follow-able.
    
    """
    if model in registry:
        return

    registry.append(model)
    
    if not field_name:
        field_name = 'target_%s' % model._meta.model_name
    
    if not related_name:
        related_name = 'follow_%s' % model._meta.model_name
    
    field = ForeignKey(model, related_name=related_name, null=True,
        blank=True, db_index=True)
    
    field.contribute_to_class(Follow, field_name)
    setattr(model, lookup_method_name, get_followers_for_object)
    model_map[model] = [related_name, field_name]
    
def follow(user, obj):
    """ Make a user follow an object """
    follow, created = Follow.objects.get_or_create(user, obj)
    return follow

def unfollow(user, obj):
    """ Make a user unfollow an object """
    try:
        follow = Follow.objects.get_follows(obj).get(user=user)
        follow.delete()
        return follow 
    except Follow.DoesNotExist:
        pass

def toggle(user, obj):
    """ Toggles a follow status. Useful function if you don't want to perform follow
    checks but just toggle it on / off. """
    if Follow.objects.is_following(user, obj):
        return unfollow(user, obj)
    return follow(user, obj)    


def follow_link(object):
    return reverse('follow.views.toggle', args=[object._meta.app_label, object._meta.object_name.lower(), object.pk])

def unfollow_link(object):
    return reverse('follow.views.toggle', args=[object._meta.app_label, object._meta.object_name.lower(), object.pk])

def toggle_link(object):
    return reverse('follow.views.toggle', args=[object._meta.app_label, object._meta.object_name.lower(), object.pk])

def follow_url(user, obj):
    """ Returns the right follow/unfollow url """
    return toggle_link(obj)




###############MODIFIED FOR PROJECTS ONLY - CONTAINS A PROJECT SPECIFIC FUNCTION

def project_toggle_link(object):
    return reverse('follow.views.project_toggle', args=[object._meta.app_label, object._meta.object_name.lower(), object.pk])

def project_follow_url(user, obj):
    """ Returns the right follow/unfollow url """
    return project_toggle_link(obj)   

def project_toggle(user, obj):
    """ Toggles a follow status. Useful function if you don't want to perform follow
    checks but just toggle it on / off. """
    if Follow.objects.is_following(user, obj):
        remove_project_from_working_projects(user, obj)
        return unfollow(user, obj)
    add_project_to_working_projects(user, obj)    
    return follow(user, obj)    


##################################################################################################    