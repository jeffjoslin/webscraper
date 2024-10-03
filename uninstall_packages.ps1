# Navigate to your project directory where requirements.txt is located
cd C:\inetpub\wwwroot\webscraper

# Read each line from requirements.txt and uninstall the package
Get-Content .\requirements.txt | ForEach-Object {
    $package = $_.Split('==')[0]  # Split the line to get the package name
    Write-Host "Uninstalling $package..."
    pip uninstall $package -y  # Uninstall the package without confirmation
}
