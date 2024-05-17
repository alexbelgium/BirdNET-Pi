<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
</style>

<?php
    $erroneous_species = file('./scripts/labels.txt', FILE_IGNORE_NEW_LINES);
    $corrected_species = file('./scripts/labels.txt', FILE_IGNORE_NEW_LINES);
    $conversion_table = file('./convert_species_list.txt', FILE_IGNORE_NEW_LINES);

    if (isset($_POST['add'])) {
        // Add species to conversion table
    } elseif (isset($_POST['restart'])) {
        // Restart server
    } elseif (isset($_POST['remove'])) {
        // Remove species from conversion table
    }
?>

<!DOCTYPE html>
<html>
<head>
    <title>Species Conversion</title>
    <script>
        function clearSelections() {
            // Clear selections in both tables
        }
    </script>
</head>
<body>
    <h1>The purpose of this page is to allow the automatic conversion of one specie with another to compensate for model bias. It SHOULD NOT be used except if you really know what you are doing and have verified manually that the misidentifications are systematic. Thanks!</h1>

    <table>
        <caption>Erroneous specie</caption>
        <!-- Populate table with erroneous species -->
    </table>

    <table>
        <caption>Corrected specie</caption>
        <!-- Populate table with corrected species -->
    </table>

    <button onclick="clearSelections();">Add specie to conversion table</button>
    <button>Restart server to start conversion</button>

    <table>
        <caption>Content of convert_species_list.txt</caption>
        <!-- Populate table with conversion table -->
    </table>
</body>
</html>
