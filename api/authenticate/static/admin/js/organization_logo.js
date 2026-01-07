django.jQuery(document).ready(function($) {
    // Mover el checkbox Clear al final del formulario de logo
    const $logoField = $('.field-logo');
    if ($logoField.length) {
        const $clearCheckbox = $logoField.find('input[type="checkbox"][id*="logo-clear"]');
        const $clearLabel = $logoField.find('label[for*="logo-clear"]');
        const $fileInput = $logoField.find('input[type="file"]');
        
        if ($clearCheckbox.length && $fileInput.length) {
            // Crear un contenedor para el checkbox y moverlo después del input de archivo
            const $checkboxContainer = $('<div style="margin-top: 10px;"></div>');
            $checkboxContainer.append($clearCheckbox);
            if ($clearLabel.length) {
                $checkboxContainer.append($clearLabel);
            }
            
            // Insertar después del input de archivo
            $fileInput.closest('li').after($checkboxContainer);
            
            // Si el checkbox estaba en otro lugar, remover su contenedor original si está vacío
            $clearCheckbox.closest('li').each(function() {
                if ($(this).children().length <= 1) {
                    $(this).remove();
                }
            });
        }
    }
});

