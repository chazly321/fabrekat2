from django.shortcuts import render, render_to_response, get_object_or_404, get_list_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.urlresolvers import reverse
from project.models import Project, ProjectImage
from projectsteps.models import PurchasedComponent, FabricatedComponent, ProjectFile, ProjectStep, StepOrder
from django.views.generic import CreateView, UpdateView, TemplateView
from project.forms import ProjectForm, ProjectImageForm, ProjectStepForm, ReOrderStepForm, TagForm, CatagoryForm, ProjectEditForm
from project.forms import   PurchasedComponentFormSet, FabricatedComponentFormSet, ProjectFileFormSet, CatagoryFormSet
from .mixins import LoginRequiredMixin
from publishedprojects.models import PublishedProject
from publishedprojects.views import publish_project
from follow import utils
from follow.models import Follow
import uuid
from projectpricer.utils import get_product
from projecttags.models import ProjectTag
from projecttags.views import tag_assign, tag_remove
from .utils import get_project_id, is_project_published, move_step_up, move_step_down, is_user_project_creator, adjust_order_for_deleted_step, delete_project
from django import forms
import autocomplete_light


#Assigns Project id to a project.  This will be uniquie and show in URL.


#Assigns components and files to a step

#LoginRequiredMixin checks if user is logged in
#This creates the first of the Project.  This is a fresh create


class ProjectCreateView(LoginRequiredMixin, CreateView):
    template_name = 'project/create.html'
    model = Project
    form_class = ProjectForm

    #Gets the forms.
    def get(self, request, *args, **kwargs):
            self.object = None
            form_class = self.get_form_class()
            form = self.get_form(form_class)
            return self.render_to_response(
                self.get_context_data(
                form = form,
                )
            )

    #Begins the posting proccess.  Returns the valid/invalid forms.     
    def post(self, request, *args, **kwargs):
        print request.is_ajax()
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)        
        if (form.is_valid()):       
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    #after valid check, saves the Project create form to the database
    def form_valid(self, form):
        self.object = form.save(commit = False)
        self.object.project_creator = self.request.user
        self.object.project_id = get_project_id()
        self.object = form.save()

        return HttpResponseRedirect('/project/edit/%s' % self.object.project_id)


    def form_invalid(self, form):
        return self.render_to_response(
            self.get_context_data(
                form = form,
            )
        )

class ProjectDetailView(TemplateView):
    template_name = 'project/pub_detail.html'

    def get_context_data(self, **kwargs):
        user_id = self.request.user.id
        context = super(ProjectDetailView, self).get_context_data(**kwargs)
        project = get_object_or_404(Project, project_id = self.kwargs['project_id'])
        project_index = project.id
        creator_id = project.project_creator.id
        purchasedcomponent = []
        fabricatedcomponent = []
        projectfile = []        


        #Project Image List
        projectimage  = list(
            ProjectImage.objects.filter(
            project_image_for_project = project_index
            )
        )
        
        #Project Step Handling
        step_list = StepOrder.objects.filter(step_order_for_project = project).order_by('order')
        step_value_list = step_list.values_list('step', flat = True)
        if step_list: 

            purchasedcomponent =PurchasedComponent.objects.filter(
                    purchased_component_for_step__in = step_value_list,
                    )

            fabricatedcomponent =FabricatedComponent.objects.filter(
                    fabricated_component_for_step__in = step_value_list,
                    )
            fabricatedcomponent_from_project_list_id = fabricatedcomponent.values_list('fabricated_component_from_project_id', flat = True)
            fabricated_component_thumbnails = ProjectImage.objects.filter(project_image_for_project__in = fabricatedcomponent_from_project_list_id).first()

            projectfile  = list(
            ProjectFile.objects.filter(
                project_file_for_step__in = step_value_list,
                )
            )

            #Tag Handling
        tags = ProjectTag.objects.filter(tag_for_project = project_index)

        context['project'] = project
        context['purchasedcomponent'] = purchasedcomponent
        context['fabricatedcomponent'] = fabricatedcomponent
        context['projectfile'] = projectfile
        context['projectstep'] = step_list
        context['projectimage'] = projectimage
        context['tags'] = tags

        return context


class PublishProjectDetailView(ProjectDetailView):
    template_name = 'project/pub_detail.html'
    
    def get_context_data(self, *args, **kwargs):
        context = super(PublishProjectDetailView, self).get_context_data(**kwargs)
        unpub_project_index = context['project']
        project = PublishedProject.objects.get(project_link = unpub_project_index)
        saved_project_count = len(Follow.objects.get_follows(project))
        context['saved_project_count'] = saved_project_count
        context['published_project_index'] = project
        return context


#View for Creating a Step for a project.
class StepCreateView(LoginRequiredMixin, CreateView):
    template_name = 'project/addstep.html'
    model = ProjectStep
    form_class = ProjectStepForm

    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        #project_id is what will show in the URL.  Unique to each project.
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, project_id = project_id)
        #project index is what will track associated objects (Steps, Components, IMages etc..)
        project_index = project.id 
        creator_id = project.project_creator.id

        #Can Redo this as a decorator......
        if user_id != creator_id:
            return HttpResponseRedirect('/')
        elif is_project_published(project_id) == True:
            return HttpResponseRedirect('/')    
        else:
            self.object = None
            form_class = self.get_form_class()
            form = self.get_form(form_class)
            purchasedcomponent_formset = PurchasedComponentFormSet
            fabricatedcomponent_formset = FabricatedComponentFormSet
            projectfile_formset = ProjectFileFormSet
            return self.render_to_response(
                self.get_context_data(
                form = form,
                purchasedcomponent_formset = purchasedcomponent_formset,
                fabricatedcomponent_formset = fabricatedcomponent_formset,
                projectfile_formset = projectfile_formset,
                )
            )

    def post(self, request, *args, **kwargs):
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)

        purchasedcomponent_formset = PurchasedComponentFormSet(self.request.POST,)  
        fabricatedcomponent_formset = FabricatedComponentFormSet(self.request.POST,)
        projectfile_formset = ProjectFileFormSet(self.request.POST, self.request.FILES,)
        print 'CHECKING VALID......'
        if (
            form.is_valid()
            and  purchasedcomponent_formset.is_valid()
            and  fabricatedcomponent_formset.is_valid()
            and  projectfile_formset.is_valid()
            ):      
            print 'VALID'
            return self.form_valid(form, purchasedcomponent_formset, fabricatedcomponent_formset, projectfile_formset)
        else:
            print 'NOT VALID'
            return self.form_invalid(form, purchasedcomponent_formset, fabricatedcomponent_formset, projectfile_formset)


    def form_valid(self, form, purchasedcomponent_formset, fabricatedcomponent_formset, projectfile_formset):
        self.object = form.save(commit = False)
        project_id = self.kwargs['project_id']
        project = Project.objects.get(project_id = project_id)
        self.object.step_for_project = project
        self.object = form.save()

        purchasedcomponent_formset.instance = self.object         #FIRST ASSIGN THE PROJECT STEP TO THE PURCHASED COMPONENT
        form = purchasedcomponent_formset.save(commit = False) #SAVE THE FORM WITH INSTANCE ATTACHED
        if form:
            form[0].product = get_product(   #ASSIGN ALL NEEDED VALUES
                self.request, 
                str(form[0].purchased_component_url_link), 
                str(form[0].purchased_component_name),
                )
        purchasedcomponent_formset.save()

        fabricatedcomponent_formset.instance = self.object
        fabricatedcomponent_formset.fabricated_component_for_project = project
        fabricatedcomponent_formset.instance.fabricated_component_name = self.object.step_for_project.project_name
        fabricatedcomponent_formset.save()

        projectfile_formset.instance = self.object
        projectfile_formset.project_file_for_project_id = project.id
        projectfile_formset.save()

        #STEP ORDER ASSIGNMENT - Get Or Create Outputs Tuple - {object, Boolean - If Created True}:
        existing_steps_for_project = StepOrder.objects.filter(step_order_for_project = project)
        count_of_existing_steps = len(existing_steps_for_project) + 1
        new_step = StepOrder.objects.create(step_order_for_project = project, step = self.object) 
        new_step.order = count_of_existing_steps
        new_step.save()


        return HttpResponseRedirect('/project/edit/%s' % project_id)


    def form_invalid(self, form, purchasedcomponent_formset, fabricatedcomponent_formset, projectfile_formset):
        return self.render_to_response(
            self.get_context_data(
                form = form,
                purchasedcomponent_formset = purchasedcomponent_formset,
                fabricatedcomponent_formset = fabricatedcomponent_formset,
                projectfile_formset = projectfile_formset,
            )
        )

#Allows upload and assigns an image to a Project via the project_index
class ImageCreateView(LoginRequiredMixin, CreateView):
    template_name = 'project/addimage.html'
    model = ProjectImage
    form_class = ProjectImageForm

    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, project_id = project_id)
        #Can Redo this as a decorator......
        if user_id != project.project_creator_id:
            return HttpResponseRedirect('/')
        elif is_project_published(project_id) == True:
            return HttpResponseRedirect('/')    
        else:
            self.object = None
            form_class = self.get_form_class()
            form = self.get_form(form_class)
            return self.render_to_response(
                self.get_context_data(
                form = form,
                )
            )

    def post(self, request, *args, **kwargs):
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        
        if (form.is_valid()):       

            return self.form_valid(form,)
        else:
            return self.form_invalid(form,)


            #Item Assigning Project to the FK does not seem to be working.
    def form_valid(self, form):
        project_id = self.kwargs['project_id']
        self.object = form.save(commit = False)
        project = Project.objects.get(project_id = project_id)
        self.object.project_image_for_project = project
        self.object = form.save()

        return HttpResponseRedirect('/project/edit/%s' % project_id)


    def form_invalid(self, form):
        return self.render_to_response(
            self.get_context_data(
                form = form,
            )
        )       

#any projects saved by user using the follows app will appear in this view.
@login_required
def my_saved_projects(request):

    my_saved_projects_id = Follow.objects.get_follows(PublishedProject).values('target_publishedproject_id')

    my_saved_projects =  Project.objects.filter(id__in = my_saved_projects_id)


    context = {
    'my_saved_projects': my_saved_projects,
    }

    return render_to_response(
        'project/saved_projects.html',
        context,
        context_instance = RequestContext(request),        
        )



#List Projects created by user.  Splits between working projects and published projects
@login_required
def my_projects(request):

    user = request.user
    user_projects =  Project.objects.filter(project_creator = user)
    my_published_projects = PublishedProject.objects.filter(project_link__in = user_projects)
    my_published_projects_id = my_published_projects.values_list('project_link_id', flat = True)
    my_unpublished_projects =  user_projects.exclude(id__in = my_published_projects_id)
    # my_unpublished_projects = Project.objects.filter(project_id__in = user_projects).exclude(project_id__in = my_published_projects)


    context = {
    'my_unpublished_projects': my_unpublished_projects,
    'my_published_projects': my_published_projects,
    }

    return render_to_response(
        'project/my_projects.html',
        context,
        context_instance = RequestContext(request),        
        )

#Edit project view is the main view for any unpublished projects.  Shows everything assigned to the project and POST buttons for edits.



class EditProjectView(ProjectDetailView, LoginRequiredMixin):
    template_name = 'project/edit.html'

    def get_context_data(self, **kwargs):
        print 'EDIT PROJECT CONTEXST DTATA'
        context = super(EditProjectView, self).get_context_data(**kwargs)
        project = context['project']
    
        form = ProjectEditForm(instance = project)
        context['form'] = form

        tag_form = TagForm
        context['tag_form'] = tag_form

        catagory_form = CatagoryFormSet()
        context['catagory_form'] = catagory_form   

        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()
        project = context['project']
        step_list = context['projectstep']
        for tag in context['tags']:
            if ('_remove_tag_%s'% tag.id) in request.POST:
                tag_remove(project, tag)   
                return HttpResponseRedirect('/project/edit/%s' % project.project_id)        
        if '_addstep' in request.POST:
            return HttpResponseRedirect('/project/edit/%s/addstep/' % project.project_id)
        
        if '_addtag' in request.POST:
            tag_assign(project, TagForm(request.POST))    
            return HttpResponseRedirect('/project/edit/%s' % project.project_id)                    
        
        elif '_publish' in request.POST:
            publish_project(project, request)
            return HttpResponseRedirect('/project/%s' % project.project_id)   
        
        elif '_save' in request.POST:
            form = ProjectEditForm(request.POST, instance=project)
            print form.errors
            print 'SAVING PROJECT.....'
            if form.is_valid():
                print 'FORM WAS VALID'
                form.save()
            else:
                print 'FORM SAVE FAILED.'
            return HttpResponseRedirect('/project/edit/%s' % project.project_id) 
        
        elif '_delete_project' in request.POST:
            delete_project(
                context['project'], 
                context['projectstep'], 
                context['tags'], 
                context['purchasedcomponent'], 
                context['fabricatedcomponent'], 
                context['projectimage'], 
                context['projectfile'],
                )
            return HttpResponseRedirect('/')    
        
        elif '_addimage' in request.POST:
            return HttpResponseRedirect('/project/edit/%s/addimage/' % project.project_id)            
        # elif '_reorder_steps' in request.POST:
        #   return HttpResponseRedirect('/project/edit/%s/ordersteps/' % project.project_id)   

        for step in step_list:
            if ('_deletestep_%s'% step.id) in request.POST:
                adjust_order_for_deleted_step(project, step, step_list)
                return HttpResponseRedirect('/project/edit/%s' % project.project_id)

            if ('_move_%s_step_up'% step.id) in request.POST:
                if step.order == 1:
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)
                else:
                    move_step_up(step_list, step)
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)
            if ('_move_%s_step_down'% step.id) in request.POST:
                if step.order == (len(step_list)):
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)
                else:
                    move_step_down(step_list, step)
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)            





# @login_required
# def edit_project(request, project_id):
#     user_id = request.user.id
#     project = get_object_or_404(Project, project_id = project_id)
#     project_index = project.id 
#     creator_id = project.project_creator.id
#     purchasedcomponent = []
#     fabricatedcomponent = []
#     projectfile = []

#     #Can Redo this as a decorator......
#     if user_id != creator_id:
#         return HttpResponseRedirect('/')
#     elif is_project_published(project_id) == True:
#         return HttpResponseRedirect('/')    
#     else:
#         form = ProjectForm(instance = project)
#         tag_form = TagForm
#         catagory_form = CatagoryFormSet

#         projectimage  = list(
#             ProjectImage.objects.filter(
#             project_image_for_project = project_index
#             )
#         )

#         step_list = StepOrder.objects.filter(step_order_for_project = project).order_by('order')
#         step_value_list = step_list.values_list('step', flat = True)


#         if step_list: 

#             purchasedcomponent =PurchasedComponent.objects.filter(
#                     purchased_component_for_step__in = step_value_list,
#                     )

#             fabricatedcomponent =FabricatedComponent.objects.filter(
#                     fabricated_component_for_step__in = step_value_list,
#                     )
#             fabricatedcomponent_from_project_list_id = fabricatedcomponent.values_list('fabricated_component_from_project_id', flat = True)
#             fabricated_component_thumbnails = ProjectImage.objects.filter(project_image_for_project__in = fabricatedcomponent_from_project_list_id).first()

#             projectfile  = list(
#             ProjectFile.objects.filter(
#                 project_file_for_step__in = step_value_list,
#                 )
#             )

#         tags = ProjectTag.objects.filter(tag_for_project = project_index)

#         for cat in tags:
#             if ('_remove_tag_%s'% cat.id) in request.POST:
#                 tag_remove(project, cat)   
#                 return HttpResponseRedirect('/project/edit/%s' % project.project_id)        
#         if request.POST:
#             if '_addstep' in request.POST:
#                 return HttpResponseRedirect('/project/edit/%s/addstep/' % project.project_id)
            
#             if '_addtag' in request.POST:
#                 tag_assign(project, TagForm(request.POST))    
#                 return HttpResponseRedirect('/project/edit/%s' % project.project_id)                    
            
#             elif '_publish' in request.POST:
#                 publish_project(project, request)   
            
#             elif '_save' in request.POST:
#                 form = ProjectForm(request.POST, instance = project)
            
#             elif '_delete_project' in request.POST:
#                 return HttpResponseRedirect('/project/edit/%s/delete/' % project.project_id)    
            
#             elif '_addimage' in request.POST:
#                 return HttpResponseRedirect('/project/edit/%s/addimage/' % project.project_id)  
#             # elif '_reorder_steps' in request.POST:
#             #   return HttpResponseRedirect('/project/edit/%s/ordersteps/' % project.project_id)       
#         for step in step_list:
#             if ('_deletestep_%s'% step.id) in request.POST:
#                 adjust_order_for_deleted_step(project, step, step_list)
#                 return HttpResponseRedirect('/project/edit/%s' % project.project_id)

#             if ('_move_%s_step_up'% step.id) in request.POST:
#                 if step.order == 1:
#                     return HttpResponseRedirect('/project/edit/%s' % project.project_id)
#                 else:
#                     move_step_up(step_list, step)
#                     return HttpResponseRedirect('/project/edit/%s' % project.project_id)
#             if ('_move_%s_step_down'% step.id) in request.POST:
#                 if step.order == (len(step_list)):
#                     return HttpResponseRedirect('/project/edit/%s' % project.project_id)
#                 else:
#                     move_step_down(step_list, step)
#                     return HttpResponseRedirect('/project/edit/%s' % project.project_id)            



#         context = {
#             'form' : form,
#             'purchasedcomponent':purchasedcomponent,
#             'fabricatedcomponent':fabricatedcomponent,              
#             'projectfile': projectfile,
#             'projectstep':step_list,
#             'projectimage':projectimage,
#             'tag_form': tag_form,
#             'tags':tags,
#             'catagory_form':catagory_form,            
#         }   


#         return render_to_response(
#             'project/edit.html',
#             context,
#             context_instance = RequestContext(request),
#             )



@login_required
def edit_step(request, id):
    user_id = request.user.id
    edited_step = get_object_or_404(ProjectStep, id=id)

    #Can Redo this as a decorator......
    # if user_id != creator_id:
    #   return HttpResponseRedirect('/')
    # elif is_project_published(project_id) == True:
    #   return HttpResponseRedirect('/')    
    # else:
    form = ProjectStepForm(instance = edited_step)
    fabricatedcomponent_form = FabricatedComponentFormSet(instance = edited_step)
    purchasedcomponent_form = PurchasedComponentFormSet(instance = edited_step)
    projectfile_form = ProjectFileFormSet(instance = edited_step)

    if request.POST:
        if '_save' in request.POST:
            form = ProjectStepForm(request.POST,request.FILES,instance = edited_step)
            fabricatedcomponent_form = FabricatedComponentFormSet(request.POST, instance = edited_step)
            purchasedcomponent_form = PurchasedComponentFormSet(request.POST,request.FILES, instance = edited_step)
            projectfile_form = ProjectFileFormSet(request.POST, request.FILES, instance = edited_step)
            if form.is_valid() and fabricatedcomponent_form.is_valid() and purchasedcomponent_form.is_valid() and projectfile_form.is_valid():          
                form.save()
                fabricatedcomponent_form.save()
                purchasedcomponent_form.save()
                projectfile_form.save()
                return HttpResponseRedirect('/project/edit/%s' % edited_step.step_for_project.project_id)                   


    context = {
        'form' : form,
        'fabricatedcomponent_form':fabricatedcomponent_form,
        'purchasedcomponent_form':purchasedcomponent_form,
        'projectfile_form':projectfile_form,
    }       


    return render_to_response(
        'project/editstep.html',
        context,
        context_instance = RequestContext(request),
        )


#Removes The step association with the project object.  Does not remove from database.
# @login_required
# def delete_step(request, *args, **kwargs):
#     user_id = request.user.id
#     deleted_step_order_object = get_object_or_404(StepOrder, step=step)
#     associated_project = project
#     if user_id != associated_project.project_creator_id:
#         return HttpResponseRedirect('/')    
#     else:

#         if request.POST:
#             if '_delete_step_confirm' in request.POST:
#                 adjust_order_for_deleted_step(associated_project, delete_step_order_object, step)
#                 return HttpResponseRedirect('/project/edit/%s' % associated_project.project_id)     
#             elif '_backto_project' in request.POST:
#                 return HttpResponseRedirect('/project/edit/%s' % associated_project.project_id) 



#         context = {
#             'projectstep' : delete_step,
#             'fabricatedcomponent':fabricatedcomponent,
#             'purchasedcomponent':purchasedcomponent,
#             'projectfile':projectfile,
#         }   


#         return render_to_response(
#             'project/deletestep.html',
#             context,
#             context_instance = RequestContext(request),
#             )

#Revision Maker:
#Pull current version data into new project, including links pictures, steps (no new assignm,ents unless asgined in revison)
#URL should be /project/NEW_RANDOM_PROJECT_SLUG
#New OneToOne Relationsip to the project that this one revised.
#a FK dict is built to represent the revison tree.
#Drawing tree level is tracked (0 for new, revison 1, 2, 3, etc.. for new revisons) on creation.
#Revisons are tracked on publishedprojects model, so trevions rolls only on published.
#Qerysets for project serach will only return the newest revions on any direect search.
#Detail page will display links to previous versions.

#NOTES TO SELF:
#One to ONe assignemtn will assign to the most recent version.  We will not support tree braches.
    #Structure could support branches, might get too complicated for user.
#Publsiehd Projects will display all revisions.
#Fabricated Components will need to save revison number that (fabricated component from project revison number)
#If someone is linked to the old revision, a banner will need to be displayed stating that this is an old version.
#Deleting/editing PROJECT STEPS will delete/edit for all revisons in the same way.

class ReviseProjectView(LoginRequiredMixin, UpdateView):
    template_name = 'project/edit.html'
    model = Project
    form_class = ProjectForm


    def get_object(self, queryset = None):
        obj = Project.objects.get(project_id = self.kwargs['project_id'])
        return obj

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        form = ProjectForm(instance = project)
        
        projectstep = ProjectStep.objects.filter(
            step_for_project = project,
            ).order_by('step_order')
        step_list = []
        for step in projectstep:
            step_list.append(step.id)

        projectimage  = list(
            ProjectImage.objects.filter(
            project_image_for_project = project
            )
        )

        purchasedcomponent =PurchasedComponent.objects.filter(
                purchased_component_for_step__in = step_list,
                )

        fabricatedcomponent =FabricatedComponent.objects.filter(
                fabricated_component_for_step__in = step_list,
                )
        fabricatedcomponent_from_project_list_id = fabricatedcomponent.values_list('fabricated_component_from_project_id', flat = True)
        fabricated_component_thumbnails = ProjectImage.objects.filter(project_image_for_project__in = fabricatedcomponent_from_project_list_id).first()

        projectfile  = list(
        ProjectFile.objects.filter(
            project_file_for_step__in = step_list,
            )
        )

        catagories = ProjectTag.objects.filter(tag_for_project = project)

        context = {
            'form':form,
            'purchasedcomponent':purchasedcomponent,
            'fabricatedcomponent':fabricatedcomponent,              
            'projectfile': projectfile,
            'projectstep':projectstep,
            'projectimage':projectimage,
            'tags':tags,
        } 
        return render_to_response(
            'project/edit.html',
            context,
            context_instance = RequestContext(request),
            )

    def dispatch(self, request, *args, **kwargs):         
        project = self.get_object()
        projectstep = ProjectStep.objects.filter(
            step_for_project = project,
            ).order_by('step_order')
     
        if '_addstep' in request.POST:
            return HttpResponseRedirect('/project/edit/%s/addstep/' % project.project_id)
            
        if '_addcatagory' in request.POST:
            print 'Checking Catagory:::::',TagForm(request.POST)
            tag_assign(project, TagForm(request.POST))    
            return HttpResponseRedirect('/project/edit/%s' % project.project_id)                    
            
        elif '_publish' in request.POST:
            publish_project(project, request)
            return HttpResponseRedirect('/project/%s' % project.project_id)   
            
        elif '_save' in request.POST:
            form = ProjectForm(request.POST, instance = project)
            
        elif '_delete_project' in request.POST:
            return HttpResponseRedirect('/project/edit/%s/delete/' % project.project_id)    
            
        elif '_addimage' in request.POST:
            return HttpResponseRedirect('/project/edit/%s/addimage/' % project.project_id)  
            # elif '_reorder_steps' in request.POST:
            #   return HttpResponseRedirect('/project/edit/%s/ordersteps/' % project.project_id)       
        for step in step_list:
            if ('_deletestep_%s'% step.id) in request.POST:
                adjust_order_for_deleted_step(step, step_list)
                return HttpResponseRedirect('/project/edit/%s' % project.project_id)

            if ('_move_%s_step_up'% step.id) in request.POST:
                if step.order == 1:
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)
                else:
                    move_step_up(step_list, step)
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)
            if ('_move_%s_step_down'% step.id) in request.POST:
                if step.order == (len(step_list)):
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)
                else:
                    move_step_down(step_list, step)
                    return HttpResponseRedirect('/project/edit/%s' % project.project_id)            
 

        return super(ReviseProjectView, self).dispatch(request, *args, **kwargs)