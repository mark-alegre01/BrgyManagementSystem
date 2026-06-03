from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Document

class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'documents/list.html'
    context_object_name = 'documents'
    
    def get_queryset(self):
        # Allow all users to see documents for now. Can restrict based on roles if needed.
        return Document.objects.all().order_by('-updated_at')

class DocumentCreateView(LoginRequiredMixin, CreateView):
    model = Document
    fields = ['title', 'document_type', 'content']
    template_name = 'documents/workspace.html'
    success_url = reverse_lazy('documents:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'New Document'
        context['document_types'] = Document.DOCUMENT_TYPES
        return context

class DocumentUpdateView(LoginRequiredMixin, UpdateView):
    model = Document
    fields = ['title', 'document_type', 'content']
    template_name = 'documents/workspace.html'
    success_url = reverse_lazy('documents:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Document'
        context['document_types'] = Document.DOCUMENT_TYPES
        return context

class DocumentDeleteView(LoginRequiredMixin, DeleteView):
    model = Document
    template_name = 'documents/confirm_delete.html'
    success_url = reverse_lazy('documents:list')

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View

class DocumentPDFView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        document = get_object_or_404(Document, pk=pk)
        
        # Render the HTML template with the document content
        html_string = render_to_string('documents/pdf_export.html', {'document': document})
        
        try:
            import weasyprint
            # Generate PDF using WeasyPrint
            pdf_file = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
            
            # Return as HTTP response with PDF content type
            response = HttpResponse(pdf_file, content_type='application/pdf')
            filename = f"{document.title or 'document'}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except OSError as e:
            # Catch the Windows GTK3 missing error (libgobject-2.0-0)
            return HttpResponse(
                "<h2>PDF Export Failed</h2>"
                "<p>WeasyPrint requires GTK3 binaries to be installed on Windows.</p>"
                f"<p>Error details: {str(e)}</p>"
                "<p>To fix this, please install the GTK3 runtime for Windows and add it to your system PATH.</p>",
                status=500
            )
