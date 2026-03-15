$ErrorActionPreference = "Stop"

$baseUrl = "https://backend-mmng.onrender.com/api"
$outputFile = "live_data_backup.json"

Write-Host "Starting data extraction from live Render API (PowerShell)..."

$backupData = @{
    messages = @()
    memories = @()
    gallery_folders = @()
    stats = @{}
}

# 1. Fetch Messages
Write-Host "Fetching messages..."
try {
    $messagesUrl = "$baseUrl/messages?limit=2000"
    $messagesRes = Invoke-RestMethod -Uri $messagesUrl -Method Get -TimeoutSec 30
    if ($messagesRes.success) {
        $backupData.messages = $messagesRes.messages
        Write-Host "✅ Fetched $($messagesRes.messages.Count) messages"
    } else {
        Write-Host "⚠️ Error fetching messages"
    }
} catch {
    Write-Host "⚠️ Failed to fetch messages: $_"
}

# 2. Fetch Memories
Write-Host "Fetching memories..."
try {
    $memoriesUrl = "$baseUrl/memories?type=all&limit=2000"
    $memoriesRes = Invoke-RestMethod -Uri $memoriesUrl -Method Get -TimeoutSec 30
    if ($memoriesRes.success) {
        $backupData.memories = $memoriesRes.memories
        Write-Host "✅ Fetched $($memoriesRes.memories.Count) memories"
    } else {
        Write-Host "⚠️ Error fetching memories"
    }
} catch {
    Write-Host "⚠️ Failed to fetch memories: $_"
}

# 3. Fetch Gallery Folders
Write-Host "Fetching gallery folders..."
try {
    $foldersUrl = "$baseUrl/gallery/folders"
    $foldersRes = Invoke-RestMethod -Uri $foldersUrl -Method Get -TimeoutSec 30
    if ($foldersRes.success) {
        $backupData.gallery_folders = $foldersRes.folders
        Write-Host "✅ Fetched $($foldersRes.folders.Count) gallery folders"
        
        # Add a property for images on each folder so we can populate it (since hash tables in powershell converted to json might be strict)
        foreach ($folder in $backupData.gallery_folders) {
            $folderName = [uri]::EscapeDataString($folder.name)
            try {
                $imagesUrl = "$baseUrl/gallery/images?folder=$folderName"
                $imagesRes = Invoke-RestMethod -Uri $imagesUrl -Method Get -TimeoutSec 30
                if ($imagesRes.success) {
                    Add-Member -InputObject $folder -MemberType NoteProperty -Name "images" -Value $imagesRes.images -Force
                    Write-Host "  - Folder '$($folder.name)': $($imagesRes.images.Count) images"
                }
            } catch {
                Write-Host "  - ⚠️ Error fetching images for folder '$folderName': $_"
            }
        }
    } else {
        Write-Host "⚠️ Error fetching gallery folders"
    }
} catch {
    Write-Host "⚠️ Failed to fetch gallery folders: $_"
}

# 4. Fetch Stats
Write-Host "Fetching general stats..."
try {
    $statsUrl = "$baseUrl/stats"
    $statsRes = Invoke-RestMethod -Uri $statsUrl -Method Get -TimeoutSec 30
    if ($statsRes.success) {
        $backupData.stats = $statsRes.stats
        Write-Host "✅ Fetched general stats"
    } else {
        Write-Host "⚠️ Error fetching stats"
    }
} catch {
    Write-Host "⚠️ Failed to fetch stats: $_"
}

# Save to file
Write-Host "`nSaving to $outputFile..."
$jsonOutput = $backupData | ConvertTo-Json -Depth 10
Set-Content -Path $outputFile -Value $jsonOutput -Encoding UTF8

$fileInfo = Get-Item $outputFile
$sizeKb = [math]::Round($fileInfo.Length / 1KB, 2)
Write-Host "🎉 Extraction complete! Saved all data ($sizeKb KB) to $outputFile"
