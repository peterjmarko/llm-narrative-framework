# Filename: tests/run_experiment.Tests.ps1

# The path to the script we are testing.
$scriptUnderTest = "$PSScriptRoot/../run_experiment.ps1"

# Dot-source the script. This is now safe because of the invocation guard.
. $scriptUnderTest

Describe 'run_experiment.ps1 Argument Handling' {

    BeforeEach {
        # This variable will store the arguments passed to our mock.
        $script:mockArgs = $null

        # To robustly mock the external 'pdm' command, we temporarily override it
        # with a function. This intercepts any call, stores the arguments, and
        # prevents the real command from running. Pester cleans this up automatically.
        function pdm {
            $script:mockArgs = $args
        }
    }

    It 'should call the python script with default arguments when no parameters are provided' {
        Invoke-Experiment
        $expectedArgs = @('run', 'python', 'src/replication_manager.py')
        $mockArgs | Should -BeExactly $expectedArgs
    }

    It 'should include the --verbose flag when -Verbose is used' {
        # We use -Verbose:$true to explicitly pass the switch parameter in a test context.
        Invoke-Experiment -Verbose:$true
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
        Invoke-Experiment -TargetDirectory 'output/combo' -StartRep 1 -EndRep 2 -Notes "Combo test" -Verbose:$true
        $expectedArgs = @(
            'run', 'python', 'src/replication_manager.py',
            'output/combo',
            '--start-rep', 1,
            '--end-rep', 2,
            '--notes', "Combo test",
            '--verbose'
        )
        # Use -BeEquivalentTo because the order of optional flags is not guaranteed.
        $mockArgs | Should -BeEquivalentTo $expectedArgs
    }
}