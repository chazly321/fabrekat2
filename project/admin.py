from django.contrib import admin
from project.models import Project, ProjectImage, Catagory
from projectsteps.models import ProjectStep, PurchasedComponent, FabricatedComponent, StepOrder


#class FabricatedComponentInline (admin.TabularInline):
#	model = FabricatedComponent
	
class PurchasedComponentInline (admin.TabularInline):
	model = PurchasedComponent

class FabricatedComponentInline(admin.TabularInline):
	model = FabricatedComponent
	fk_name = 'fabricated_component_for_project'

class ProjectStepOrderInline(admin.TabularInline):
	model = StepOrder	

class ProjectImageInline(admin.TabularInline):
	model = ProjectImage	



class ProjectAdmin (admin.ModelAdmin):
	inlines = [
	FabricatedComponentInline,
	ProjectStepOrderInline,
	ProjectImageInline,
	]

# Register your models here. 
admin.site.register(Project, ProjectAdmin)
admin.site.register(PurchasedComponent)
admin.site.register(FabricatedComponent)
admin.site.register(Catagory)
