(function() {
    var dataSetToRunFor;

    dhis2.util.on(dhis2.de.event.dataValuesLoaded, function(event, ds) {
        if (dataSetToRunFor && dataSetToRunFor !== ds) {
            console.log('PEPFAR: MER | ' + dataSetToRunFor + ' does not match ' + ds + ' resetting custom JS.');
            qbert.reset();
            meany.reset();
        } else {
            dataSetToRunFor = ds;
            stella.load();
            qbert.load();
            meany.load();

            console.log('PEPFAR: MER | Custom JS Loaded: v20170717');

            $(".PEPFAR_Form_EntryField").find(".entryfield").addClass("PEPFAR_Form_EntryField_input");
            $(".PEPFAR_Form_OptionSet").find(".entryoptionset").addClass("PEPFAR_Form_EntryField_optionset");
            $(".PEPFAR_Form_Narrative").find(".entryarea").addClass("PEPFAR_Form_EntryField_narrative");

            $('.entryfield').each(function(index) {
                if ($(this).css('background-color') != 'rgb(255, 255, 255)' && !$(this).hasClass("disabled")) {
                    $(this).css('background-color', 'rgb(255, 255, 255)');
                }
            });

            //Data Values Loaded extra js to run
            //#dataValuesLoaded#
        }
    });

    dhis2.util.on(dhis2.de.event.formReady, function(event, ds) {
        cerulean.load();

        //Form ready extra js to run
        //#formReady#
    });
})();


dhis2.util.on(dhis2.de.event.dataValueSaved, function(event, ds, dv) {
    stella.changed(dv);
    meany.changed(dv);

    //dataValueSaved extra JS to run
    //#dataValueSaved#
});