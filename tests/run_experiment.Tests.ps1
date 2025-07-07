# Filename: tests/run_experiment.Tests.ps1

# --- Test Setup ---
# The path to the script we are testing.
$scriptUnderTest = "$PSScriptRoot/../run_experiment.ps1"

# Dot-source the script to make its function available for testing.
# This is safe because the script's logic is wrapped in a function.
. $scriptUnderTest

# --- Test Suite ---
Describe 'run_experiment.ps1 Argument Handling' {

    # This block runs before each test ('It' block).
    # We define a shared mock for the 'pdm' command here.
    # The mock captures the arguments passed to it into a variable.
    BeforeEach {
        # This variable will store the arguments passed to our mock.
        $mockArgs = $null

        # To robustly mock an external command like 'pdm.exe', we override it
        # with a temporary function. This function intercepts any call to 'pdm',
        # stores the arguments passed to it in our test variable, and prevents
        # the real command from running. Pester automatically cleans up this
        # function after each test.
        function pdm {
            $script:mockArgs = $args
        }
    }

    It 'should call the python script with default arguments when no parameters are provided' {
        # Run the function with no parameters.
        Invoke-Experiment

        # Define the arguments we expect the python script to receive.
        $expectedArgs = @('run', 'python', 'src/replication_manager.py')

        # Assert that the mocked command received the exact arguments we expected.
        $mockArgs | Should -BeExactly $expectedArgs
    }

    It 'should include the --verbose flag when -Verbose is used' {
        Invoke-Experiment -Verbose
        $expectedArgs = @('run', 'python', 'src/replication_manager.py', '--verbose')
        $mockArgs | Should -BeExactly $expectedArgs
    }

    It 'should include the target directory as the first argument' {
        Invoke-Experiment -TargetDirectory 'output/test_dir'
        $expectedArgs = @('run', 'python', 'src/replication_manager.py', 'output/test_dir')
        $mockArgs | Should -BeExactly $expectedArgs
    }

    It 'should include --start-rep and --end-rep flags' {
        Invoke-Experiment -StartRep 5 -EndRep 10
        $expectedArgs = @('run', 'python', 'src/replication_manager.py', '--start-rep', 5, '--end-rep', 10)
        $mockArgs | Should -BeExactly $expectedArgs
    }

    It 'should include the --notes flag with its value' {
        Invoke-Experiment -Notes "My test run"
        $expectedArgs = @('run', 'python', 'src/replication_manager.py', '--notes', "My test run")
        $mockArgs | Should -BeExactly $expectedArgs
    }

    It 'should handle a combination of all parameters correctly' {
        Invoke-Experiment -TargetDirectory 'output/combo' -StartRep 1 -EndRep 2 -Notes "Combo test" -Verbose
        $expectedArgs = @(
            'run', 'python', 'src/replication_manager.py',
            'output/combo',
            '--start-rep', 1,
            '--end-rep', 2,
            '--notes', "Combo test",
            '--verbose'
        )
        # Use -EquivalentTo because the order of optional flags is not guaranteed to be the same.
        $mockArgs | Should -BeEquivalentTo $expectedArgs
    }
}