<?php

// ---- IMPORTS ----
//------------------------------------------------------------------------------
// Check if authenticated
require_once $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
// Get init.php 
require dirname(__FILE__).'/../server/init.php';
// ---- IMPORTS ----


// Helper function to get GraphQL URL (you can replace this with environment variables)
function getGraphQLUrl() {
    $port = getSettingValue("GRAPHQL_PORT");  // Port for the GraphQL server
    if (empty($port) || !is_numeric($port)) {
        $port = 20211;
    }
    return "0.0.0.0:$port/graphql";  // Full URL to the GraphQL endpoint
}

// Function to make a GraphQL query
function queryGraphQL($query, $variables = null) {
    $url = getGraphQLUrl();
    
    // Prepare the request data
    $data = [
        'query' => $query
    ];

    // prepare header
    $api_token = getSettingValue("API_TOKEN");
    $headers = [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $api_token  // Add Authorization header
    ];


    // Add variables if provided
    if ($variables) {
        $data['variables'] = $variables;
    }

    // Encode the data as JSON
    $dataJson = json_encode($data);

    // Initialize cURL
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $dataJson);

    // Execute the request and handle errors
    $response = curl_exec($ch);
    if ($response === false) {
        error_log('GraphQL Request Error: ' . curl_error($ch));
        return ["error" => "Request failed (GraphQL server might be down). URL: " .$url . "  Error: ". curl_error($ch)];
    }

    curl_close($ch);
    return json_decode($response, true);  // Decode and return the JSON response
}

//------------------------------------------------------------------------------
// Handle incoming requests
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Decode the JSON input from the AJAX request
    $input = json_decode(file_get_contents('php://input'), true);
    
    // Ensure the query is set
    if (!isset($input['query'])) {
        echo json_encode(['error' => 'No query provided']);
        exit;
    }

    // Extract the query and variables
    $query = $input['query'];
    $variables = isset($input['variables']) ? $input['variables'] : null;

    // Call the GraphQL function
    $result = queryGraphQL($query, $variables);

    // Send the response back to the client
    header('Content-Type: application/json');
    echo json_encode($result);
}
?>
