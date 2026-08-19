django.jQuery(document).ready(function($) {
    const $logoField = $('.field-logo');
    if ($logoField.length) {
        const $clearCheckbox = $logoField.find('input[type="checkbox"][id*="logo-clear"]');
        const $clearLabel = $logoField.find('label[for*="logo-clear"]');
        const $fileInput = $logoField.find('input[type="file"]');
        
        if ($clearCheckbox.length && $fileInput.length) {
            const $checkboxContainer = $('<div style="margin-top: 10px;"></div>');
            $checkboxContainer.append($clearCheckbox);
            if ($clearLabel.length) {
                $checkboxContainer.append($clearLabel);
            }
            
            $fileInput.closest('li').after($checkboxContainer);
            
            $clearCheckbox.closest('li').each(function() {
                if ($(this).children().length <= 1) {
                    $(this).remove();
                }
            });
        }
    }
});
